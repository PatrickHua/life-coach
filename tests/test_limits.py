from datetime import datetime, timedelta, timezone

from harness import config as C
from harness import limits

NOW = datetime(2026, 11, 4, 10, tzinfo=timezone.utc)


def state(**kw):
    s = {"timezone": "UTC", "quiet_start": "22:00", "quiet_end": "08:00", "paused": False,
         "initiated": [], "recent_texts": [], "awaiting_reply": False, "followups": 0}
    s.update(kw)
    return s


def msg(text="Hi", **kw):
    return {"type": "send_message", "text": text, "why": "test", **kw}


def reason(action, s=None, is_reply=False, now=NOW):
    r = limits.check_message(action, now, s or state(), is_reply)
    return r and r[0]


def test_ok():
    assert reason(msg()) is None


def test_content_rules():
    assert reason(msg("x" * 281)) == "too_long"
    assert reason(msg("x" * 280)) is None
    assert reason(msg(more=["x" * 281])) == "too_long"
    assert reason(msg(more=["a"] * 6)) == "too_many_pages"
    assert reason(msg(buttons=list("abcde"))) == "too_many_buttons"
    assert reason(msg(buttons=["x" * 21])) == "button_too_long"
    assert reason({"type": "send_message", "text": "hi"}) == "missing_why"
    assert reason(msg(why="x" * 141)) == "too_long"


def test_quiet_hours_and_pause():
    late = NOW.replace(hour=23)
    assert reason(msg(), now=late) == "quiet_hours"
    assert reason(msg(), now=NOW.replace(hour=7, minute=59)) == "quiet_hours"
    assert reason(msg(), now=NOW.replace(hour=8)) is None
    assert reason(msg(), s=state(paused=True)) == "paused"
    assert reason(msg(), now=late, is_reply=True) is None  # replies are always allowed


def test_daily_cap_and_gap():
    three = [(NOW - timedelta(hours=h)).isoformat() for h in (9, 6, 3)]
    assert reason(msg(), s=state(initiated=three)) == "over_daily_cap"
    recent = [(NOW - timedelta(minutes=30)).isoformat()]
    assert reason(msg(), s=state(initiated=recent)) == "min_gap"
    assert reason(msg(), s=state(initiated=recent), is_reply=True) is None
    yesterday = [(NOW - timedelta(days=1, hours=h)).isoformat() for h in (1, 2, 3)]
    assert reason(msg(), s=state(initiated=yesterday)) is None


def test_double_text():
    assert reason(msg(), s=state(awaiting_reply=True, followups=0)) is None
    assert reason(msg(), s=state(awaiting_reply=True, followups=1)) == "double_text"


def test_duplicate():
    s = state(recent_texts=[[(NOW - timedelta(hours=1)).isoformat(), "Hi"]])
    assert reason(msg("Hi"), s=s, is_reply=True) == "duplicate"
    s = state(recent_texts=[[(NOW - timedelta(hours=25)).isoformat(), "Hi"]])
    assert reason(msg("Hi"), s=s) is None


def test_fix_length_splits_at_sentences():
    text = " ".join(f"Sentence {i} is here." for i in range(60))
    fixed = limits.fix_length(msg(text))
    assert len(fixed["text"]) <= C.MAX_TEXT and fixed["text"].endswith(".")
    assert 1 <= len(fixed["more"]) <= C.MAX_PAGES
    assert all(len(p) <= C.MAX_TEXT for p in fixed["more"])
    assert limits.check_content(fixed) is None


def test_clean_strips_headings():
    assert limits.clean("## Plan\n**Run** today") == "Plan\nRun today"
