import json

from conftest import events_of, onboard_with_goal

from harness import config as C
from harness.core import SNAG


async def test_crash_then_recover(make_harness):
    h, t = await make_harness()
    await onboard_with_goal(h, t)
    await h.on_text("crash")
    assert t.last == SNAG and events_of(h, "agent_died")
    await h.on_command("pause")  # harness commands still work
    assert t.last.startswith("Paused")
    await h.on_text("hello again")
    assert t.last.startswith("You said: hello again")  # restarted agent answers


async def test_timeout(make_harness):
    h, t = await make_harness(timeout=1.0)
    await onboard_with_goal(h, t)
    await h.on_text("slow")
    assert t.last == SNAG and events_of(h, "turn_timeout")
    await h.on_text("still there?")
    assert t.last.startswith("You said")


async def test_crisis_bypasses_agent(make_harness):
    h, t = await make_harness()
    await onboard_with_goal(h, t)
    n_events = len(events_of(h, "event"))
    await h.on_text("honestly I want to die")
    assert "crisis line" in t.last and h.state["paused"]
    assert len(events_of(h, "event")) == n_events  # never reached the agent


async def test_agent_isolation(make_harness, tmp_path, monkeypatch):
    agent_dir = C.ROOT / "agents" / "_probe"
    agent_dir.mkdir(exist_ok=True)
    try:
        (agent_dir / "manifest.json").write_text(json.dumps({"name": "_probe", "command": ["python3", "{agent_dir}/a.py"]}))
        (agent_dir / "a.py").write_text(
            "import json,os,sys\n"
            "for line in sys.stdin:\n"
            "    ev=json.loads(line)\n"
            "    if ev['type']=='user_message':\n"
            "        info={'cwd':os.getcwd(),'token':os.environ.get('TELEGRAM_BOT_TOKEN')}\n"
            "        print(json.dumps({'type':'send_message','text':json.dumps(info)[:280],'why':'probe'}),flush=True)\n"
            "        sys.stdin.readline()\n"
            "    print('not json, should be ignored',flush=True)\n"
            "    print(json.dumps({'type':'done','event_id':ev['id']}),flush=True)\n")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret")
        h, t = await make_harness(agent="_probe")
        h.state["onboarded"] = True
        await h.on_text("probe")
        info = json.loads(t.last)
        assert info["token"] is None
        assert info["cwd"] == str(h.agent.state_dir)
        assert events_of(h, "agent_noise")
    finally:
        for f in agent_dir.iterdir():
            f.unlink()
        agent_dir.rmdir()


async def test_state_survives_restart(make_harness, tmp_path, clock):
    h, t = await make_harness()
    cid = await onboard_with_goal(h, t)
    await h.agent.stop()
    h2, t2 = await make_harness()
    assert h2.state["onboarded"] and cid in h2.state["contracts"]


PROBE_BAD = (
    "import json,sys\n"
    "for line in sys.stdin:\n"
    "    ev=json.loads(line)\n"
    "    if ev['type']=='user_message':\n"
    "        print(json.dumps({'type':'send_message'}),flush=True)\n"
    "        r=json.loads(sys.stdin.readline())\n"
    "        print(json.dumps({'type':'send_message','text':r['type']+':'+r['reason'],'why':'probe'}),flush=True)\n"
    "        sys.stdin.readline()\n"
    "    print(json.dumps({'type':'done','event_id':ev['id']}),flush=True)\n")


async def test_invalid_action_gets_rejected_reply(make_harness):
    agent_dir = C.ROOT / "agents" / "_bad"
    agent_dir.mkdir(exist_ok=True)
    try:
        (agent_dir / "manifest.json").write_text(json.dumps({"name": "_bad", "command": ["python3", "{agent_dir}/a.py"]}))
        (agent_dir / "a.py").write_text(PROBE_BAD)
        h, t = await make_harness(agent="_bad")
        h.state["onboarded"] = True
        await h.on_text("hi")
        assert t.last == "rejected:invalid_schema"
    finally:
        for f in agent_dir.iterdir():
            f.unlink()
        agent_dir.rmdir()


async def test_bad_timestamp_is_rejected_not_fatal(make_harness):
    from harness.core import Turn
    h, t = await make_harness()
    sent = []

    async def capture(ev):
        sent.append(ev)
    real_send, h.agent.send = h.agent.send, capture
    await h.dispatch({"type": "schedule_wakeup", "at": "tomorrow-ish", "note": "x"}, Turn("e", True))
    assert sent[-1]["type"] == "rejected" and sent[-1]["reason"] == "invalid_schema"
    h.agent.send = real_send
