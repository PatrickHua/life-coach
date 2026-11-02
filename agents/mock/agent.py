"""Mock agent: tests the harness plumbing, not coaching.

Keywords it understands (in any message): help, buttons, long, remind, calendar, propose,
done, slow, crash. Anything else gets echoed back with a message count kept in its own memory.
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

MEMORY = Path("memory.json")  # cwd is this agent's private state folder
HELP_PAGES = [
    "help: this list · buttons: three buttons to tap · long: a too-long message, to test the length rules",
    "remind: a reminder in ~1 minute · calendar: today's events · propose: suggest a calendar event tomorrow",
    "done: ask the harness to check whether your goal is achieved · slow: take too long · crash: exit",
]


def write(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def read():
    line = sys.stdin.readline()
    if not line:
        sys.exit(0)
    return json.loads(line)


def act(obj):
    """Write one action and return the harness's one reply."""
    write(obj)
    return read()


def say(text, why, buttons=None, more=None):
    msg = {"type": "send_message", "text": text, "why": why}
    if buttons:
        msg["buttons"] = buttons
    if more:
        msg["more"] = more
    return act(msg)


def remember():
    data = json.loads(MEMORY.read_text()) if MEMORY.exists() else {"messages": 0}
    data["messages"] += 1
    MEMORY.write_text(json.dumps(data))
    return data["messages"]


def on_text(text, ctx):
    t = text.lower()
    now = datetime.fromisoformat(ctx["now"])
    active = [c for c in ctx["contracts"] if c["status"] in ("active", "verifying")]
    if "help" in t or "what can you do" in t:
        say("I'm the mock agent. I test the plumbing, I don't coach. Tap More for my keywords.",
            "user asked for help", more=HELP_PAGES)
    elif "button" in t:
        say("Pick a colour:", "testing buttons", buttons=["Red", "Green", "Blue"])
    elif "long" in t:
        long_text = " ".join(f"This is sentence number {i} of a message that is far too long." for i in range(1, 12))
        reply = say(long_text, "testing the length limit")
        if reply["type"] == "rejected":  # retry with the same text: the harness should split it
            say(long_text, "testing the length limit (retry)")
    elif "remind" in t:
        at = now + timedelta(minutes=1)
        reply = act({"type": "schedule_wakeup", "at": at.isoformat(),
                     "note": f"the reminder you asked for at {now:%H:%M:%S}"})
        if reply["type"] == "accepted":
            say(f"OK, I'll ping you around {at:%H:%M} (if the harness's limits allow it).", "confirm reminder")
        else:
            say(f"The harness refused the reminder: {reply['reason']}", "report rejection")
    elif "calendar" in t:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        reply = act({"type": "get_calendar", "req_id": "cal1", "start": start.isoformat(),
                     "end": (start + timedelta(days=1)).isoformat()})
        if reply["type"] == "rejected":
            say(f"No calendar for me: {reply['reason']}", "report rejection")
        else:
            events = reply["events"]
            titles = ", ".join(e["title"] for e in events[:3]) or "nothing"
            say(f"Today you have {len(events)} event(s): {titles}"[:280], "user asked about calendar")
    elif "propose" in t:
        start = (now + timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
        reply = act({"type": "propose_event", "req_id": "p1", "title": "Mock run", "start": start.isoformat(),
                     "end": (start + timedelta(minutes=30)).isoformat(), "why": "testing proposals"})
        if reply["type"] == "rejected":
            say(f"The harness refused the proposal: {reply['reason']}", "report rejection")
    elif "done" in t or "finished" in t or "did it" in t:
        if not active:
            say("You have no active goal. Use /goal first.", "no contract to verify")
            return
        reply = act({"type": "request_verification", "contract_id": active[0]["id"],
                     "why": "user said they finished"})
        if reply["type"] == "rejected":
            say(f"The harness won't ask yet: {reply['reason']} ({reply.get('detail', '')})", "report rejection")
    elif "slow" in t:
        time.sleep(3600)
    elif "crash" in t:
        os._exit(1)  # skip the finally: a real crash sends no "done"
    else:
        n = remember()
        say(f"You said: {text[:200]} (message #{n} I remember)", "echo", buttons=["👍"])


def handle(ev):
    kind, ctx = ev["type"], ev["context"]
    if kind == "contract_assigned":
        c = ev["contract"]
        say(f"Got your goal: {c['goal']}. I'm a mock coach, so I'll just help test things. Say 'help'.",
            "acknowledge new goal", buttons=["help"])
    elif kind == "user_message":
        on_text(ev["text"], ctx)
    elif kind == "button_tap":
        if ev["choice"] in ("Red", "Green", "Blue"):
            say(f"You picked {ev['choice']}.", "button test result")
        else:
            on_text(ev["choice"], ctx)
    elif kind == "wakeup":
        reply = say(f"⏰ Reminder: {ev['note']}", "scheduled reminder", buttons=["👍"])
        if reply["type"] == "rejected":
            print(f"reminder blocked: {reply['reason']}", file=sys.stderr)
    elif kind == "proposal_result":
        say("You added it. 👍" if ev["accepted"] else "OK, not added.", "proposal outcome")
    elif kind == "verification_result":
        say(f"Verification answer: {ev['answer']}.", "report verification")
    elif kind == "contract_closed":
        result = "achieved" if ev["achieved"] else "not achieved"
        print(f"contract {ev['contract_id']} closed: {result} after {ev['days']} days", file=sys.stderr)
    elif kind == "user_feedback":
        print("user flagged my last message", file=sys.stderr)


def main():
    while True:
        ev = read()
        try:
            handle(ev)
        finally:
            write({"type": "done", "event_id": ev["id"]})


if __name__ == "__main__":
    main()
