"""End to end with the real mock agent as a subprocess."""
from conftest import events_of, onboard_with_goal

from harness import config as C


async def test_onboarding_and_goal_form(make_harness):
    h, t = await make_harness()
    await h.on_text("hello")
    assert t.last == "Send /start to begin."
    await h.on_command("start")
    assert any("calendar" in m.lower() for m in t.texts())
    cid = await onboard_with_goal(h, t)
    assert cid.startswith("c_")
    assert "Got your goal: Run 3x a week" in t.last  # the agent got contract_assigned
    assert h.state["contracts"][cid]["agent"] == h.agent.version


async def test_cancel_form_freezes_nothing(make_harness):
    h, t = await make_harness()
    await h.on_command("start")
    await h.on_command("goal")
    await h.on_text("Read a book")
    await h.on_command("cancel")
    assert h.state["form"] is None and h.state["contracts"] == {}


async def test_echo_buttons_and_memory(make_harness):
    h, t = await make_harness()
    await onboard_with_goal(h, t)
    await h.on_text("hi there")
    assert t.last == "You said: hi there (message #1 I remember)"
    await h.on_text("again")
    assert "#2" in t.last  # the agent's own memory file persists
    await h.on_text("buttons")
    await h.on_button(t.button("Green"))
    assert t.last == "You picked Green."
    await h.on_button(t.button("Green"))  # buttons are one-tap only
    assert t.last == "That button isn't active any more."


async def test_long_message_is_split_behind_more(make_harness):
    h, t = await make_harness()
    await onboard_with_goal(h, t)
    await h.on_text("long")
    assert [r["reason"] for r in events_of(h, "rejected")] == ["too_long"]
    assert events_of(h, "auto_split")
    mid, text, buttons = t.messages[-1]
    assert len(text) <= C.MAX_TEXT
    assert [b[0] for b in buttons] == ["More ▾"]
    before = len(t.messages)
    await h.on_button(t.button("More ▾"))
    assert len(t.messages) == before + 1 and len(t.last) <= C.MAX_TEXT


async def test_help_uses_more_pages(make_harness):
    h, t = await make_harness()
    await onboard_with_goal(h, t)
    await h.on_text("help")
    pages = 0
    while True:
        try:
            bid = t.button("More ▾")
        except AssertionError:
            break
        if bid not in h.state["buttons"]:
            break
        await h.on_button(bid)
        pages += 1
    assert pages == 3


async def test_wakeup_and_min_gap(make_harness, clock):
    h, t = await make_harness()
    await onboard_with_goal(h, t)
    await h.on_text("remind me")
    assert "ping you" in t.last
    clock.advance(seconds=61)
    await h.tick()
    assert t.last.startswith("⏰ Reminder")
    assert h.state["awaiting_reply"] is True
    await h.on_text("remind me")
    assert "ping you" in t.last
    clock.advance(seconds=61)
    await h.tick()
    assert sum(m.startswith("⏰") for m in t.texts()) == 1  # second one blocked: 2h minimum gap
    assert events_of(h, "rejected")[-1]["reason"] == "min_gap"


async def test_wakeups_wait_while_paused(make_harness, clock):
    h, t = await make_harness()
    await onboard_with_goal(h, t)
    await h.on_text("remind me")
    await h.on_command("pause")
    clock.advance(minutes=5)
    await h.tick()
    assert not t.last.startswith("⏰")
    await h.on_command("resume")
    await h.tick()
    assert t.last.startswith("⏰")


async def test_why_and_bad(make_harness):
    h, t = await make_harness()
    await onboard_with_goal(h, t)
    await h.on_text("hey")
    await h.on_command("why")
    assert t.last.endswith(": echo")
    await h.on_command("bad")
    assert events_of(h, "user_feedback")


async def test_export_and_forget(make_harness):
    h, t = await make_harness()
    await onboard_with_goal(h, t)
    await h.on_command("export")
    assert t.files and t.files[0].endswith(".zip")
    await h.on_command("forget")
    await h.on_button(t.button("🗑 Delete everything"))
    assert h.state["contracts"] == {} and not h.state["onboarded"]
    assert not list(h.store.contracts_dir.iterdir())
    await h.on_command("start")
    await h.on_command("goal")
    assert "New goal" in t.last  # still works after wiping
