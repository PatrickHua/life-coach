from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from harness import config as C
from harness.agent_process import AgentProcess
from harness.core import Harness
from harness.store import Store


class FakeTransport:
    def __init__(self):
        self.messages = []  # (message_id, text, [(label, button_id)])
        self.files = []

    async def send(self, text, buttons=None):
        mid = str(len(self.messages) + 1)
        self.messages.append((mid, text, list(buttons or [])))
        return mid

    async def clear_buttons(self, message_id):
        pass

    async def typing(self):
        pass

    async def send_file(self, path, caption=""):
        self.files.append(Path(path).name)

    @property
    def last(self):
        return self.messages[-1][1]

    def texts(self):
        return [m[1] for m in self.messages]

    def button(self, label):
        """Id of the most recent button with this label."""
        for _, _, buttons in reversed(self.messages):
            for lab, bid in buttons:
                if lab == label:
                    return bid
        raise AssertionError(f"no button {label!r} in {self.texts()[-3:]}")


class FakeCalendar:
    connected = True
    status = "✅ Fake calendar."

    def __init__(self):
        self.events, self.created, self.deleted = [], [], []

    async def list_events(self, start, end):
        return self.events

    async def create_event(self, title, start, end):
        self.created.append((title, start, end))
        return f"ev{len(self.created)}"

    async def delete_event(self, event_id):
        self.deleted.append(event_id)


class Clock:
    def __init__(self):
        self.now = datetime(2026, 11, 4, 10, 0, tzinfo=timezone.utc)  # a Wednesday, 10:00

    def __call__(self):
        return self.now

    def advance(self, **kw):
        self.now += timedelta(**kw)


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
async def make_harness(tmp_path, clock):
    made = []

    async def make(agent="mock", calendar=None, timeout=5.0):
        settings = C.Settings(timezone="UTC", quiet_start="22:00", quiet_end="08:00",
                              data_dir=tmp_path / "data", state_root=tmp_path / "agent_state",
                              turn_timeout=timeout)
        transport = FakeTransport()
        store = Store(settings.data_dir)
        proc = AgentProcess(C.ROOT / "agents", agent, settings.state_root)
        h = Harness(settings, transport, calendar or NoCal(), proc, store, clock=clock)
        await h.start()
        made.append(h)
        return h, transport

    yield make
    for h in made:
        await h.agent.stop()


class NoCal:
    connected = False
    status = "Calendar is off."

    async def list_events(self, start, end):
        return []

    async def create_event(self, *a):
        raise RuntimeError("no calendar")

    async def delete_event(self, *a):
        raise RuntimeError("no calendar")


async def onboard_with_goal(h, t, goal="Run 3x a week", evidence="My word is enough", deadline="2 weeks"):
    await h.on_command("start")
    await h.on_command("goal")
    await h.on_text(goal)
    await h.on_text("12 runs logged")
    await h.on_button(t.button(deadline))
    await h.on_button(t.button(evidence))
    await h.on_button(t.button("✅ Lock it in"))
    return next(iter(h.state["contracts"]))


def events_of(h, kind):
    return [r for r in h.store.read_jsonl(h.store.events_path) if r["kind"] == kind]
