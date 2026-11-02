"""Message and request rules. Each check returns None (allowed) or (reason, detail)."""
import re
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from . import config as C


def local(now: datetime, tz: str) -> datetime:
    return now.astimezone(ZoneInfo(tz))


def in_quiet_hours(now: datetime, state: dict) -> bool:
    t = local(now, state["timezone"]).time()
    start, end = time.fromisoformat(state["quiet_start"]), time.fromisoformat(state["quiet_end"])
    if start <= end:
        return start <= t < end
    return t >= start or t < end


def initiated_today(now: datetime, state: dict) -> int:
    today = local(now, state["timezone"]).date()
    return sum(1 for ts in state["initiated"]
               if local(datetime.fromisoformat(ts), state["timezone"]).date() == today)


def messages_left_today(now: datetime, state: dict) -> int:
    return max(0, C.DAILY_CAP - initiated_today(now, state))


def check_content(action: dict):
    text, more, buttons = action["text"], action.get("more") or [], action.get("buttons") or []
    why = action.get("why", "")
    if not why.strip():
        return "missing_why", "every message needs a why"
    if len(why) > C.MAX_WHY:
        return "too_long", f"why is {len(why)}/{C.MAX_WHY}"
    if len(text) > C.MAX_TEXT:
        return "too_long", f"{len(text)}/{C.MAX_TEXT}, put the rest in more"
    if len(more) > C.MAX_PAGES:
        return "too_many_pages", f"{len(more)}/{C.MAX_PAGES} pages"
    for i, page in enumerate(more):
        if len(page) > C.MAX_TEXT:
            return "too_long", f"more[{i}] is {len(page)}/{C.MAX_TEXT}"
    if len(buttons) > C.MAX_BUTTONS:
        return "too_many_buttons", f"{len(buttons)}/{C.MAX_BUTTONS}"
    for label in buttons:
        if len(label) > C.MAX_BUTTON_LABEL:
            return "button_too_long", f"{label[:25]!r} is {len(label)}/{C.MAX_BUTTON_LABEL}"
    return None


def check_initiated(now: datetime, state: dict):
    """Rules for anything the agent starts on its own (not a reply to the user)."""
    if state["paused"]:
        return "paused", "the user paused check-ins"
    if in_quiet_hours(now, state):
        return "quiet_hours", f"quiet hours {state['quiet_start']}-{state['quiet_end']}"
    if initiated_today(now, state) >= C.DAILY_CAP:
        return "over_daily_cap", f"{C.DAILY_CAP} per day"
    if state["initiated"]:
        last = datetime.fromisoformat(state["initiated"][-1])
        if now - last < timedelta(hours=C.MIN_GAP_HOURS):
            return "min_gap", f"last one {int((now - last).total_seconds() // 60)} min ago, need {C.MIN_GAP_HOURS}h"
    if state["awaiting_reply"] and state["followups"] >= 1:
        return "double_text", "user hasn't replied; one follow-up already sent"
    return None


def check_duplicate(now: datetime, state: dict, text: str):
    cutoff = now - timedelta(hours=C.DUPLICATE_HOURS)
    for ts, old in state["recent_texts"]:
        if old == text and datetime.fromisoformat(ts) > cutoff:
            return "duplicate", "same text sent in the last 24h"
    return None


def check_message(action: dict, now: datetime, state: dict, is_reply: bool):
    return (check_content(action)
            or (None if is_reply else check_initiated(now, state))
            or check_duplicate(now, state, action["text"]))


_HEADING = re.compile(r"^\s*#{1,6}\s*", re.M)


def clean(text: str) -> str:
    """No headings or bold in chat: strip the markers, keep the words."""
    return _HEADING.sub("", text).replace("**", "").strip()


def split_text(text: str, limit: int = C.MAX_TEXT) -> list[str]:
    """Cut text into pages at sentence (or word) boundaries."""
    pages, rest = [], text.strip()
    while len(rest) > limit:
        window = rest[:limit]
        cut = max(window.rfind(". "), window.rfind("! "), window.rfind("? "), window.rfind("\n"))
        cut = cut + 1 if cut > limit // 3 else (window.rfind(" ") if window.rfind(" ") > 0 else limit)
        pages.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    if rest:
        pages.append(rest)
    return pages


def fix_length(action: dict) -> dict:
    """Last resort after a retry: overview in text, the rest behind [More]."""
    pages = split_text(action["text"])
    for page in action.get("more") or []:
        pages.extend(split_text(page))
    fixed = dict(action, text=pages[0], more=pages[1:1 + C.MAX_PAGES])
    if len(action.get("why", "")) > C.MAX_WHY:
        fixed["why"] = action["why"][:C.MAX_WHY]
    return fixed
