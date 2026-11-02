"""The harness: owns the user, the calendar, contracts, verification and every rule.

The agent is reached only through `run_turn`. Everything the user sees passes through here.
"""
import asyncio
import json
import shutil
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Protocol

import jsonschema

from . import config as C
from . import contract as contracts
from . import limits, safety
from .agent_process import AgentDied, AgentProcess
from .store import Store

PROTOCOL_DIR = C.ROOT / "protocol"
ACTIONS_SCHEMA = json.loads((PROTOCOL_DIR / "actions.schema.json").read_text())
ACTION_VALIDATOR = jsonschema.Draft202012Validator(ACTIONS_SCHEMA)

HELP = (
    "Commands: /goal set a goal · /goals your goals · /done check off a goal · /pause · /resume · "
    "/why last message's reason · /undo last calendar add · /bad flag the last message · "
    "/log recent harness activity · /export · /forget"
)
SNAG = "Sorry, I hit a snag. Try again in a bit."


class Transport(Protocol):
    async def send(self, text: str, buttons: list[tuple[str, str]] | None = None) -> str: ...
    async def clear_buttons(self, message_id: str) -> None: ...
    async def typing(self) -> None: ...
    async def send_file(self, path: Path, caption: str = "") -> None: ...


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Turn:
    def __init__(self, event_id: str, is_reply: bool):
        self.event_id = event_id
        self.is_reply = is_reply
        self.message_rejects = 0


class Harness:
    def __init__(self, settings: C.Settings, transport: Transport, calendar, agent: AgentProcess,
                 store: Store | None = None, clock: Callable[[], datetime] = utcnow):
        self.settings = settings
        self.transport = transport
        self.calendar = calendar
        self.agent = agent
        self.store = store or Store(settings.data_dir)
        self.clock = clock
        self.lock = asyncio.Lock()
        self.state = self.store.load_state() or self._fresh_state()

    # ---------- state ----------

    def _fresh_state(self) -> dict:
        return {
            "onboarded": False, "paused": False, "timezone": self.settings.timezone,
            "quiet_start": self.settings.quiet_start, "quiet_end": self.settings.quiet_end,
            "next_id": 1, "awaiting_reply": False, "followups": 0,
            "initiated": [], "recent_texts": [], "last_agent_message": None,
            "buttons": {}, "wakeups": {}, "contracts": {}, "form": None,
            "awaiting_evidence": None, "confirmed_events": [],
        }

    def save(self) -> None:
        now = self.clock()
        keep = (now - timedelta(days=2)).isoformat()
        self.state["initiated"] = [t for t in self.state["initiated"] if t > keep]
        self.state["recent_texts"] = [r for r in self.state["recent_texts"] if r[0] > keep]
        self.store.save_state(self.state)

    def new_id(self, prefix: str) -> str:
        n = self.state["next_id"]
        self.state["next_id"] = n + 1
        return f"{prefix}{n}"

    def log(self, kind: str, **fields) -> None:
        self.store.log({"ts": self.clock().isoformat(), "kind": kind, **fields})

    def local_now(self) -> datetime:
        return limits.local(self.clock(), self.state["timezone"])

    def parse_time(self, value: str) -> datetime:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=self.local_now().tzinfo)
        return dt

    def contract_list(self) -> list[dict]:
        out = []
        for c in contracts.load_all(self.store):
            info = self.state["contracts"].get(c["id"], {})
            status = info.get("status", "active")
            if status == "active" and (info.get("pending") or info.get("deadline_asked")):
                status = "verifying"
            out.append({k: c[k] for k in ("id", "goal", "done_means", "deadline", "evidence")} | {"status": status})
        return out

    def context(self) -> dict:
        now = self.clock()
        return {
            "now": self.local_now().isoformat(timespec="seconds"),
            "timezone": self.state["timezone"],
            "quiet_hours": {"start": self.state["quiet_start"], "end": self.state["quiet_end"]},
            "in_quiet_hours": limits.in_quiet_hours(now, self.state),
            "messages_left_today": limits.messages_left_today(now, self.state),
            "awaiting_reply": self.state["awaiting_reply"],
            "paused": self.state["paused"],
            "contracts": self.contract_list(),
        }

    def event(self, type_: str, **fields) -> dict:
        return {"type": type_, "id": self.new_id("e"), "ts": self.clock().isoformat(timespec="seconds"),
                "context": self.context(), **fields}

    # ---------- talking to the user ----------

    async def say(self, text: str, buttons: list[tuple[str, dict]] | None = None) -> str:
        """Send a harness message. Each button is (label, payload); payloads are kept server-side."""
        ids = [(label, self.new_id("b")) for label, _ in buttons or []]
        mid = await self.transport.send(text, [(label, bid) for label, bid in ids] or None)
        for (label, bid), (_, payload) in zip(ids, buttons or []):
            self.state["buttons"][bid] = {"label": label, "message": mid,
                                          "created": self.clock().isoformat(), **payload}
        self.log("harness_message", text=text, buttons=[b[0] for b in buttons or []], message_id=mid)
        return mid

    async def clear_message_buttons(self, mid: str) -> None:
        for bid in [b for b, info in self.state["buttons"].items() if info["message"] == mid]:
            del self.state["buttons"][bid]
        await self.transport.clear_buttons(mid)

    # ---------- the agent ----------

    async def start(self) -> None:
        await self.agent.start()
        self.log("agent_started", agent=self.agent.version)
        async with self.lock:
            await self.run_turn("start", is_reply=False, agent_version=self.agent.version)
            self.save()

    async def run_turn(self, type_: str, is_reply: bool, **fields) -> None:
        if is_reply:
            await self.transport.typing()
        ev = self.event(type_, **fields)
        turn = Turn(ev["id"], is_reply)
        self.log("event", event=ev)
        deadline = asyncio.get_running_loop().time() + self.settings.turn_timeout
        try:
            await self.agent.send(ev)
            while True:
                action = await self.agent.read(deadline - asyncio.get_running_loop().time())
                if isinstance(action, str):
                    self.log("agent_noise", line=action[:500])
                    continue
                self.log("action", action=action)
                errors = sorted(ACTION_VALIDATOR.iter_errors(action), key=str)
                if errors:
                    await self.reply_inline("rejected", action=str(action.get("type")), reason="invalid_schema",
                                            detail=errors[0].message[:200], req_id=action.get("req_id"))
                    continue
                if action["type"] == "done":
                    return
                pause = asyncio.get_running_loop().time()
                await self.dispatch(action, turn)
                if action["type"] == "get_calendar":  # time waiting on Google doesn't count
                    deadline += asyncio.get_running_loop().time() - pause
        except asyncio.TimeoutError:
            self.log("turn_timeout", event_id=ev["id"], agent=self.agent.version)
            await self.agent.restart()
            if is_reply:
                await self.say(SNAG)
        except AgentDied as e:
            self.log("agent_died", event_id=ev["id"], agent=self.agent.version, error=str(e))
            await self.agent.restart()
            if is_reply:
                await self.say(SNAG)

    async def reply_inline(self, type_: str, **fields) -> None:
        """Every action except `done` gets exactly one reply event, inside the same turn."""
        fields = {k: v for k, v in fields.items() if v is not None}
        ev = self.event(type_, **fields)
        self.log("event", event=ev)
        await self.agent.send(ev)

    async def reject(self, action: dict, reason: str, detail: str = "") -> None:
        self.log("rejected", action=action["type"], reason=reason, detail=detail)
        await self.reply_inline("rejected", action=action["type"], reason=reason, detail=detail,
                                req_id=action.get("req_id"))

    async def accept(self, action: dict) -> None:
        await self.reply_inline("accepted", action=action["type"], req_id=action.get("req_id"))

    async def dispatch(self, action: dict, turn: Turn) -> None:
        handler = getattr(self, "act_" + action["type"])
        try:
            await handler(action, turn)
        except ValueError as e:  # e.g. a timestamp that isn't ISO 8601
            await self.reject(action, "invalid_schema", str(e)[:200])

    # ---------- actions ----------

    async def act_send_message(self, a: dict, turn: Turn) -> None:
        now = self.clock()
        problem = limits.check_message(a, now, self.state, turn.is_reply)
        if problem:
            reason, detail = problem
            turn.message_rejects += 1
            if turn.message_rejects >= 2 and reason in ("too_long", "too_many_pages"):
                a = limits.fix_length(a)
                problem = limits.check_message(a, now, self.state, turn.is_reply)
                self.log("auto_split", original_reason=reason)
            if problem:
                await self.reject(a, *problem)
                return
        text, more = limits.clean(a["text"]), [limits.clean(p) for p in a.get("more") or []]
        buttons = [(label, {"kind": "agent", "choice": label}) for label in a.get("buttons") or []]
        if more:
            buttons.append(("More ▾", {"kind": "more", "pages": more}))
        mid = await self.say(text, buttons)
        self.state["last_agent_message"] = {"id": mid, "text": text, "why": a["why"]}
        self.state["recent_texts"].append([now.isoformat(), a["text"]])
        if not turn.is_reply:
            self.state["initiated"].append(now.isoformat())
            if self.state["awaiting_reply"]:
                self.state["followups"] += 1
            self.state["awaiting_reply"] = True
        await self.reply_inline("message_sent", req_id=a.get("req_id") or "", message_id=mid)

    async def act_schedule_wakeup(self, a: dict, turn: Turn) -> None:
        at = self.parse_time(a["at"])
        if at <= self.clock():
            return await self.reject(a, "wakeup_in_past", a["at"])
        if len(self.state["wakeups"]) >= C.MAX_WAKEUPS:
            return await self.reject(a, "too_many_wakeups", f"max {C.MAX_WAKEUPS} pending")
        wid = a.get("wakeup_id") or self.new_id("w")
        self.state["wakeups"][wid] = {"at": at.astimezone(timezone.utc).isoformat(), "note": a["note"]}
        await self.accept(a | {"req_id": a.get("req_id") or wid})

    async def act_cancel_wakeup(self, a: dict, turn: Turn) -> None:
        if self.state["wakeups"].pop(a["wakeup_id"], None) is None:
            return await self.reject(a, "unknown_wakeup", a["wakeup_id"])
        await self.accept(a)

    async def act_get_calendar(self, a: dict, turn: Turn) -> None:
        start, end = self.parse_time(a["start"]), self.parse_time(a["end"])
        if end <= start or end - start > timedelta(days=C.CALENDAR_MAX_DAYS):
            return await self.reject(a, "calendar_range", f"end after start, max {C.CALENDAR_MAX_DAYS} days")
        try:
            events = await self.calendar.list_events(start, end)
        except Exception as e:  # Google errors must not kill the turn
            self.log("calendar_error", error=str(e)[:300])
            return await self.reject(a, "calendar_unavailable", "couldn't reach the calendar")
        await self.reply_inline("calendar", req_id=a["req_id"], events=events)

    async def act_propose_event(self, a: dict, turn: Turn) -> None:
        if not self.calendar.connected:
            return await self.reject(a, "calendar_unavailable", "no calendar connected")
        start, end = self.parse_time(a["start"]), self.parse_time(a["end"])
        if end <= start or start <= self.clock():
            return await self.reject(a, "calendar_range", "event must be in the future and end after it starts")
        problem = None if turn.is_reply else limits.check_initiated(self.clock(), self.state)
        if problem:
            return await self.reject(a, *problem)
        ls, le = limits.local(start, self.state["timezone"]), limits.local(end, self.state["timezone"])
        text = f"Add “{a['title']}” on {ls:%a %d %b}, {ls:%H:%M}–{le:%H:%M} to your Coach calendar?"
        payload = {"kind": "proposal", "proposal_id": a["req_id"], "title": a["title"],
                   "start": start.isoformat(), "end": end.isoformat()}
        await self.say(text, [("✅ Add", payload | {"accept": True}), ("❌ No", payload | {"accept": False})])
        if not turn.is_reply:
            self.state["initiated"].append(self.clock().isoformat())
        await self.accept(a)

    async def act_request_verification(self, a: dict, turn: Turn) -> None:
        cid, now = a["contract_id"], self.clock()
        info = self.state["contracts"].get(cid)
        if info is None:
            return await self.reject(a, "unknown_contract", cid)
        if info["status"] != "active":
            return await self.reject(a, "contract_closed", cid)
        if info.get("pending") or info.get("deadline_asked"):
            return await self.reject(a, "verify_pending", "waiting for the user's answer")
        if info["verify_requests"]:
            last = datetime.fromisoformat(info["verify_requests"][-1])
            if now - last < timedelta(days=C.VERIFY_GAP_DAYS):
                return await self.reject(a, "verify_too_soon", f"one request per {C.VERIFY_GAP_DAYS} days")
        problem = None if turn.is_reply else limits.check_initiated(now, self.state)
        if problem:
            return await self.reject(a, *problem)
        info["verify_requests"].append(now.isoformat())
        self.store.append(self.store.verifications_path,
                          {"ts": now.isoformat(), "contract_id": cid, "source": "agent", "why": a["why"]})
        await self.ask_verification(cid, source="agent")
        if not turn.is_reply:
            self.state["initiated"].append(now.isoformat())
        await self.accept(a)

    async def act_flag(self, a: dict, turn: Turn) -> None:
        self.log("flag", flag=a["kind"], detail=a.get("detail", ""))
        await self.accept(a)
        if a["kind"] == "crisis":
            await self.crisis()

    # ---------- verification ----------

    async def ask_verification(self, cid: str, source: str) -> None:
        c = contracts.load(self.store, cid)
        payload = {"kind": "verify", "contract_id": cid, "source": source}
        if source == "deadline":
            text = f"Deadline reached for: {c['goal']} (done means: {c['done_means']}). Did you achieve it?"
            buttons = [("✅ Achieved", payload | {"answer": "achieved"}),
                       ("❌ Not achieved", payload | {"answer": "gave_up"})]
        else:
            text = f"Goal check: {c['goal']} (done means: {c['done_means']}). Did you achieve it?"
            buttons = [("✅ Achieved", payload | {"answer": "achieved"}),
                       ("⏳ Not yet", payload | {"answer": "not_yet"}),
                       ("❌ Gave up", payload | {"answer": "gave_up"})]
        mid = await self.say(text, buttons)
        info = self.state["contracts"][cid]
        stamp = {"asked": self.clock().isoformat(), "message": mid, "source": source}
        if source == "deadline":
            if info.get("pending"):
                await self.clear_message_buttons(info["pending"]["message"])
                info["pending"] = None
            info["deadline_asked"] = stamp
        else:
            info["pending"] = stamp

    async def answer_verification(self, cid: str, answer: str, source: str) -> None:
        info = self.state["contracts"][cid]
        info["pending"] = None
        self.store.append(self.store.verifications_path,
                          {"ts": self.clock().isoformat(), "contract_id": cid, "source": source, "answer": answer})
        if answer == "achieved" and contracts.load(self.store, cid)["evidence"] == "link":
            self.state["awaiting_evidence"] = {"contract_id": cid, "source": source}
            await self.say("🎉 Nice! Send me the link that shows it's done.")
            return
        await self.finish_verification(cid, answer, source)

    async def finish_verification(self, cid: str, answer: str, source: str) -> None:
        if source != "deadline":
            await self.run_turn("verification_result", is_reply=True, contract_id=cid, answer=answer)
        if answer == "not_yet":
            await self.say("No problem, keep going. 💪")
            return
        await self.close_contract(cid, achieved=(answer == "achieved"), how=f"{source}:{answer}")

    async def close_contract(self, cid: str, achieved: bool, how: str) -> None:
        c = contracts.load(self.store, cid)
        info = self.state["contracts"][cid]
        info.update(status="closed", pending=None)
        if info.get("deadline_asked"):
            await self.clear_message_buttons(info["deadline_asked"]["message"])
            info["deadline_asked"] = None
        now = self.clock()
        days = round((now - datetime.fromisoformat(c["created"])).total_seconds() / 86400, 2)
        outcome = {"ts": now.isoformat(), "contract_id": cid, "agent": info["agent"],
                   "achieved": achieved, "days": days, "how": how}
        self.store.append(self.store.outcomes_path, outcome)
        self.log("contract_closed", **outcome)
        await self.say(("✅ Logged as achieved: " if achieved else "Logged as not achieved: ") + c["goal"])
        await self.run_turn("contract_closed", is_reply=False, contract_id=cid, achieved=achieved, days=days)

    async def receive_evidence(self, text: str) -> None:
        pending = self.state["awaiting_evidence"]
        cid = pending["contract_id"]
        if not text.strip().lower().startswith(("http://", "https://")):
            await self.say("That doesn't look like a link. Send one starting with http(s)://, or /skip to answer later.")
            return
        self.state["awaiting_evidence"] = None
        self.store.append(self.store.evidence_dir / f"{cid}.jsonl", {"ts": self.clock().isoformat(), "link": text.strip()})
        await self.finish_verification(cid, "achieved", pending["source"])

    # ---------- inbound from the user ----------

    async def on_text(self, text: str) -> None:
        async with self.lock:
            self.log("user_message", text=text)
            if safety.is_crisis(text):
                await self.crisis()
            elif self.state["awaiting_evidence"]:
                await self.receive_evidence(text)
            elif self.state["form"]:
                await self.form_text(text)
            elif not self.state["onboarded"]:
                await self.say("Send /start to begin.")
            else:
                self.state["awaiting_reply"], self.state["followups"] = False, 0
                await self.run_turn("user_message", is_reply=True, text=text)
            self.save()

    async def on_button(self, bid: str) -> None:
        async with self.lock:
            info = self.state["buttons"].get(bid)
            if info is None:
                await self.say("That button isn't active any more.")
                self.save()
                return
            await self.clear_message_buttons(info["message"])
            self.log("button_tap", label=info["label"], button_kind=info["kind"])
            await getattr(self, "tap_" + info["kind"])(info)
            self.save()

    async def tap_agent(self, info: dict) -> None:
        self.state["awaiting_reply"], self.state["followups"] = False, 0
        age = self.clock() - datetime.fromisoformat(info["created"])
        if age > timedelta(hours=C.BUTTON_EXPIRY_HOURS):
            await self.say("That one's old, here's where we are now.")
            await self.run_turn("user_message", is_reply=True, text=f"(tapped an expired button: {info['choice']})")
        else:
            await self.run_turn("button_tap", is_reply=True, message_id=info["message"], choice=info["choice"])

    async def tap_more(self, info: dict) -> None:
        first, rest = info["pages"][0], info["pages"][1:]
        await self.say(first, [("More ▾", {"kind": "more", "pages": rest})] if rest else None)

    async def tap_verify(self, info: dict) -> None:
        cid = info["contract_id"]
        if self.state["contracts"][cid]["status"] != "active":
            await self.say("That goal is already closed.")
            return
        await self.answer_verification(cid, info["answer"], info["source"])

    async def tap_proposal(self, info: dict) -> None:
        accepted = info["accept"]
        if accepted:
            try:
                eid = await self.calendar.create_event(info["title"], datetime.fromisoformat(info["start"]),
                                                       datetime.fromisoformat(info["end"]))
                self.state["confirmed_events"].append({"id": eid, "title": info["title"]})
                await self.say(f"📅 Added “{info['title']}”. /undo removes it.")
            except Exception as e:
                self.log("calendar_error", error=str(e)[:300])
                await self.say("I couldn't add that to your calendar.")
                accepted = False
        await self.run_turn("proposal_result", is_reply=True, proposal_id=info["proposal_id"], accepted=accepted)

    async def tap_form(self, info: dict) -> None:
        await self.form_choice(info["field"], info["value"])

    async def tap_forget(self, info: dict) -> None:
        if not info["confirm"]:
            await self.say("Okay, nothing deleted.")
            return
        await self.agent.stop()
        self.store.wipe()
        shutil.rmtree(self.agent.state_dir, ignore_errors=True)
        self.agent.state_dir.mkdir(parents=True, exist_ok=True)
        self.state = self._fresh_state()
        await self.agent.start()
        await self.say("Everything's deleted (your calendar connection stays). Send /start to begin again.")

    async def tap_done_pick(self, info: dict) -> None:
        await self.start_user_verification(info["contract_id"])

    async def crisis(self) -> None:
        self.state["paused"] = True
        self.log("crisis_response")
        await self.say(safety.CRISIS_MESSAGE)

    # ---------- the goal form ----------

    async def form_text(self, text: str) -> None:
        form = self.state["form"]
        text = text.strip()
        if form["step"] == "goal":
            if len(text) > 200:
                return await self.say("Keep it under 200 characters, please.")
            form.update(goal=text, step="done_means")
            await self.say("How will we know it's done? Something you could clearly say yes or no to.")
        elif form["step"] == "done_means":
            if len(text) > 200:
                return await self.say("Keep it under 200 characters, please.")
            form.update(done_means=text, step="deadline")
            await self.ask_deadline()
        elif form["step"] == "deadline":
            try:
                d = date.fromisoformat(text)
            except ValueError:
                return await self.say("Send a date like 2026-12-01, or tap a button.")
            await self.form_choice("deadline", d.isoformat())
        else:
            await self.say("Tap one of the buttons above, or /cancel.")

    async def ask_deadline(self) -> None:
        today = self.local_now().date()
        options = [("1 week", 7), ("2 weeks", 14), ("4 weeks", 28)]
        await self.say("When's the deadline? Tap one, or send a date (YYYY-MM-DD).",
                       [(label, {"kind": "form", "field": "deadline",
                                 "value": (today + timedelta(days=n)).isoformat()}) for label, n in options])

    async def form_choice(self, field: str, value) -> None:
        form = self.state["form"]
        if not form:
            return await self.say("That form is closed. /goal starts a new one.")
        if field == "deadline":
            if date.fromisoformat(value) <= self.local_now().date():
                return await self.say("The deadline has to be after today.")
            form.update(deadline=value, step="evidence")
            await self.say("How will you show it's done?", [
                ("My word is enough", {"kind": "form", "field": "evidence", "value": "self_report"}),
                ("I'll send a link", {"kind": "form", "field": "evidence", "value": "link"})])
        elif field == "evidence":
            form.update(evidence=value, step="confirm")
            proof = "your word" if value == "self_report" else "a link"
            await self.say(f"Goal: {form['goal']}\nDone means: {form['done_means']}\nDeadline: {form['deadline']}\n"
                           f"Proof: {proof}\n\nLock it in? You can't edit it afterwards.",
                           [("✅ Lock it in", {"kind": "form", "field": "confirm", "value": True}),
                            ("❌ Cancel", {"kind": "form", "field": "confirm", "value": False})])
        elif field == "confirm":
            self.state["form"] = None
            if not value:
                return await self.say("Cancelled. /goal starts over.")
            c = contracts.freeze(self.store, form["goal"], form["done_means"], form["deadline"],
                                 form["evidence"], self.clock())
            self.state["contracts"][c["id"]] = {"status": "active", "agent": self.agent.version,
                                                "verify_requests": [], "pending": None, "deadline_asked": None}
            self.log("contract_frozen", contract=c, agent=self.agent.version)
            await self.say("🔒 Locked in. Your coach takes it from here. /done when you've achieved it.")
            await self.run_turn("contract_assigned", is_reply=True, contract={
                k: c[k] for k in ("id", "goal", "done_means", "deadline", "evidence")} | {"status": "active"})

    # ---------- commands (work even if the agent is broken) ----------

    async def on_command(self, cmd: str, args: str = "") -> None:
        async with self.lock:
            self.log("command", command=cmd, args=args)
            handler = getattr(self, "cmd_" + cmd, None)
            if handler is None:
                await self.say("I don't know that command. " + HELP)
            elif not self.state["onboarded"] and cmd not in ("start", "help", "forget", "export", "log"):
                await self.say("Send /start first.")
            else:
                await handler(args)
            self.save()

    async def cmd_start(self, args: str) -> None:
        if self.state["onboarded"]:
            await self.say("You're all set. " + HELP)
            return
        await self.say("Hi! I'm Lifecoach. I help you reach the goals you set, and I keep messages short.")
        await self.say(f"Step 1: your calendar. {self.calendar.status}")
        await self.say(f"Step 2: your timezone is {self.state['timezone']}, and I stay quiet "
                       f"{self.state['quiet_start']}–{self.state['quiet_end']}. Change these in .env if they're wrong.")
        self.state["onboarded"] = True
        await self.say("Step 3: set your first goal with /goal")

    async def cmd_help(self, args: str) -> None:
        await self.say(HELP)

    async def cmd_goal(self, args: str) -> None:
        self.state["form"] = {"step": "goal"}
        await self.say("New goal! What do you want to achieve? One sentence. (/cancel to stop)")

    async def cmd_cancel(self, args: str) -> None:
        if self.state["form"]:
            self.state["form"] = None
            await self.say("Goal form cancelled.")
        else:
            await self.say("Nothing to cancel.")

    async def cmd_skip(self, args: str) -> None:
        pending = self.state["awaiting_evidence"]
        if not pending:
            return await self.say("Nothing to skip.")
        self.state["awaiting_evidence"] = None
        await self.say("Okay. /done when you have the link.")
        await self.finish_verification(pending["contract_id"], "not_yet", pending["source"])

    async def cmd_goals(self, args: str) -> None:
        items = self.contract_list()
        if not items:
            return await self.say("No goals yet. /goal sets one.")
        icon = {"active": "🟢", "verifying": "❓", "closed": "⚪"}
        outcomes = {o["contract_id"]: o for o in self.store.read_jsonl(self.store.outcomes_path)}
        lines = []
        for c in items:
            extra = ""
            if c["id"] in outcomes:
                extra = " ✅" if outcomes[c["id"]]["achieved"] else " ✗"
            lines.append(f"{icon[c['status']]} {c['goal']} (by {c['deadline']}){extra}")
        pages = limits.split_text("\n".join(lines))
        await self.say(pages[0], [("More ▾", {"kind": "more", "pages": pages[1:]})] if pages[1:] else None)

    async def cmd_done(self, args: str) -> None:
        active = [c for c in self.contract_list() if c["status"] in ("active", "verifying")]
        if not active:
            return await self.say("No open goals. /goal sets one.")
        if len(active) == 1:
            return await self.start_user_verification(active[0]["id"])
        await self.say("Which one?", [(c["goal"][:20], {"kind": "done_pick", "contract_id": c["id"]})
                                      for c in active[:C.MAX_BUTTONS]])

    async def start_user_verification(self, cid: str) -> None:
        info = self.state["contracts"][cid]
        for key in ("pending", "deadline_asked"):
            if info.get(key):
                await self.clear_message_buttons(info[key]["message"])
                info[key] = None
        self.store.append(self.store.verifications_path,
                          {"ts": self.clock().isoformat(), "contract_id": cid, "source": "user"})
        await self.ask_verification(cid, source="user")

    async def cmd_pause(self, args: str) -> None:
        self.state["paused"] = True
        await self.say("Paused. I won't check in until you send /resume.")

    async def cmd_resume(self, args: str) -> None:
        self.state["paused"] = False
        await self.say("Welcome back! Check-ins are on again.")

    async def cmd_why(self, args: str) -> None:
        last = self.state["last_agent_message"]
        await self.say(f"Reason for “{last['text'][:60]}”: {last['why']}" if last else "No coach messages yet.")

    async def cmd_undo(self, args: str) -> None:
        if not self.state["confirmed_events"]:
            return await self.say("Nothing to undo.")
        ev = self.state["confirmed_events"].pop()
        try:
            await self.calendar.delete_event(ev["id"])
            await self.say(f"Removed “{ev['title']}” from your Coach calendar.")
        except Exception as e:
            self.log("calendar_error", error=str(e)[:300])
            self.state["confirmed_events"].append(ev)
            await self.say("I couldn't remove it. Try again later.")

    async def cmd_bad(self, args: str) -> None:
        last = self.state["last_agent_message"]
        if not last:
            return await self.say("No coach messages yet.")
        self.log("user_feedback", message_id=last["id"], agent=self.agent.version)
        await self.say("Thanks, noted. 🙏")
        await self.run_turn("user_feedback", is_reply=False, message_id=last["id"], kind="thumbs_down")

    async def cmd_log(self, args: str) -> None:
        records = self.store.read_jsonl(self.store.events_path)
        shown = [r for r in records if r["kind"] in ("rejected", "auto_split", "turn_timeout", "agent_died",
                                                    "contract_closed", "flag", "calendar_error")][-5:]
        if not shown:
            return await self.say("Nothing notable yet.")
        lines = []
        for r in shown:
            t = limits.local(datetime.fromisoformat(r["ts"]), self.state["timezone"]).strftime("%H:%M")
            detail = r.get("reason") or r.get("original_reason") or r.get("error") or r.get("flag") or ""
            lines.append(f"{t} {r['kind']} {r.get('action', '')} {detail}".strip())
        pages = limits.split_text("\n".join(lines))
        await self.say(pages[0], [("More ▾", {"kind": "more", "pages": pages[1:]})] if pages[1:] else None)

    async def cmd_export(self, args: str) -> None:
        path = self.store.dir.parent / f"lifecoach-export-{self.local_now():%Y%m%d-%H%M}.zip"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            for f in self.store.dir.rglob("*"):
                if f.is_file() and f.parent != self.store.calendar_dir:
                    z.write(f, f.relative_to(self.store.dir.parent))
        await self.transport.send_file(path, "All your Lifecoach data.")
        path.unlink()

    async def cmd_forget(self, args: str) -> None:
        await self.say("Delete all your goals, logs and the coach's memory? This can't be undone.",
                       [("🗑 Delete everything", {"kind": "forget", "confirm": True}),
                        ("Keep it", {"kind": "forget", "confirm": False})])

    # ---------- the clock ----------

    async def tick(self) -> None:
        async with self.lock:
            now = self.clock()
            for wid, w in sorted(self.state["wakeups"].items(), key=lambda kv: kv[1]["at"]):
                if datetime.fromisoformat(w["at"]) <= now and not self.state["paused"]:
                    del self.state["wakeups"][wid]
                    await self.run_turn("wakeup", is_reply=False, wakeup_id=wid, note=w["note"])
            today = self.local_now().date()
            for cid, info in list(self.state["contracts"].items()):
                if info["status"] != "active":
                    continue
                pending = info.get("pending")
                if pending and now - datetime.fromisoformat(pending["asked"]) > timedelta(hours=C.VERIFY_EXPIRY_HOURS):
                    await self.clear_message_buttons(pending["message"])
                    info["pending"] = None
                    self.log("verification_expired", contract_id=cid)
                    if pending["source"] == "agent":
                        await self.run_turn("verification_result", is_reply=False, contract_id=cid, answer="not_yet")
                asked = info.get("deadline_asked")
                if asked:
                    if now - datetime.fromisoformat(asked["asked"]) > timedelta(hours=C.DEADLINE_ANSWER_HOURS):
                        await self.close_contract(cid, achieved=False, how="deadline:no_answer")
                    continue
                deadline = date.fromisoformat(contracts.load(self.store, cid)["deadline"])
                if today > deadline and not limits.in_quiet_hours(now, self.state):
                    await self.ask_verification(cid, source="deadline")
            self.save()
