from conftest import FakeCalendar, events_of, onboard_with_goal


async def test_propose_needs_a_calendar(make_harness):
    h, t = await make_harness()
    await onboard_with_goal(h, t)
    await h.on_text("propose")
    assert "calendar_unavailable" in t.last


async def test_nothing_written_without_yes(make_harness):
    cal = FakeCalendar()
    h, t = await make_harness(calendar=cal)
    await onboard_with_goal(h, t)
    await h.on_text("propose")
    assert t.messages[-1][1].startswith("Add “Mock run”")
    assert not cal.created
    await h.on_button(t.button("❌ No"))
    assert not cal.created and t.last == "OK, not added."
    await h.on_text("propose")
    await h.on_button(t.button("✅ Add"))
    assert [c[0] for c in cal.created] == ["Mock run"]
    assert t.last == "You added it. 👍"
    await h.on_command("undo")
    assert cal.deleted == ["ev1"]


async def test_calendar_read_and_range(make_harness):
    cal = FakeCalendar()
    cal.events = [{"start": "2026-11-04T09:00:00+00:00", "end": "2026-11-04T09:30:00+00:00",
                   "title": "Standup", "busy": True, "coach": False}]
    h, t = await make_harness(calendar=cal)
    await onboard_with_goal(h, t)
    await h.on_text("calendar")
    assert t.last == "Today you have 1 event(s): Standup"
    turn_action = {"type": "get_calendar", "req_id": "r", "start": "2026-11-01T00:00:00+00:00",
                   "end": "2026-12-15T00:00:00+00:00"}
    from harness.core import Turn
    sent = []

    async def capture(ev):
        sent.append(ev)
    h.agent.send = capture
    await h.dispatch(turn_action, Turn("e", True))
    assert sent[-1]["type"] == "rejected" and sent[-1]["reason"] == "calendar_range"
