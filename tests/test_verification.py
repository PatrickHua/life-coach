from datetime import timedelta

from conftest import events_of, onboard_with_goal

from harness.scorer import scores


async def test_agent_asks_user_answers(make_harness, clock):
    h, t = await make_harness()
    cid = await onboard_with_goal(h, t)
    await h.on_text("I'm done!")
    assert t.last.startswith("Goal check: Run 3x a week")  # harness wording, not the agent's
    await h.on_text("done again")
    assert "verify_pending" in t.last
    await h.on_button(t.button("⏳ Not yet"))
    assert h.state["contracts"][cid]["status"] == "active"
    assert any("Verification answer: not_yet" in m for m in t.texts())
    await h.on_text("done")
    assert "verify_too_soon" in t.last
    clock.advance(days=3, minutes=1)
    await h.on_text("done")
    clock.advance(hours=2)
    await h.on_button(t.button("✅ Achieved"))
    assert h.state["contracts"][cid]["status"] == "closed"
    [outcome] = h.store.read_jsonl(h.store.outcomes_path)
    assert outcome["achieved"] and outcome["days"] == 3.08 and outcome["agent"] == h.agent.version
    [row] = scores(h.store)
    assert row["achieved"] == 1 and row["success_rate"] == 1.0


async def test_gave_up(make_harness):
    h, t = await make_harness()
    cid = await onboard_with_goal(h, t)
    await h.on_command("done")
    await h.on_button(t.button("❌ Gave up"))
    assert h.state["contracts"][cid]["status"] == "closed"
    assert not h.store.read_jsonl(h.store.outcomes_path)[0]["achieved"]


async def test_link_evidence(make_harness):
    h, t = await make_harness()
    cid = await onboard_with_goal(h, t, evidence="I'll send a link")
    await h.on_command("done")
    await h.on_button(t.button("✅ Achieved"))
    assert "Send me the link" in t.last
    await h.on_text("not a link")
    assert "doesn't look like a link" in t.last
    await h.on_text("https://strava.com/activities/1")
    assert h.state["contracts"][cid]["status"] == "closed"
    assert (h.store.evidence_dir / f"{cid}.jsonl").exists()


async def test_unanswered_request_expires(make_harness, clock):
    h, t = await make_harness()
    cid = await onboard_with_goal(h, t)
    await h.on_text("done")
    clock.advance(hours=49)
    await h.tick()
    assert h.state["contracts"][cid]["pending"] is None
    assert events_of(h, "verification_expired")


async def test_deadline_backstop(make_harness, clock):
    h, t = await make_harness()
    cid = await onboard_with_goal(h, t, deadline="1 week")
    clock.advance(days=7)
    await h.tick()
    assert not any(m.startswith("Deadline reached") for m in t.texts())  # deadline day itself: not yet
    clock.advance(days=1)
    await h.tick()
    assert t.last.startswith("Deadline reached for: Run 3x a week")
    await h.on_text("done")
    assert "verify_pending" in t.last  # agent can't add its own question on top
    clock.advance(hours=73)
    await h.tick()
    assert h.state["contracts"][cid]["status"] == "closed"
    assert h.store.read_jsonl(h.store.outcomes_path)[0]["how"] == "deadline:no_answer"


async def test_deadline_waits_for_quiet_hours(make_harness, clock):
    h, t = await make_harness()
    await onboard_with_goal(h, t, deadline="1 week")
    clock.advance(days=8)
    clock.now = clock.now.replace(hour=23)
    await h.tick()
    assert not t.last.startswith("Deadline reached")
    clock.advance(hours=10)
    await h.tick()
    assert t.last.startswith("Deadline reached")
