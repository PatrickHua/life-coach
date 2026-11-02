"""Chat with the harness in your terminal, no Telegram needed.

    python -m tools.fake_user            # uses .env settings, data in data-terminal/
Type messages or /commands. Tap a button by typing its number, e.g. 2.
"""
import asyncio
import sys
from pathlib import Path

from harness import config as C
from harness.agent_process import AgentProcess
from harness.calendar import make_calendar
from harness.core import Harness
from harness.store import Store


class TerminalTransport:
    def __init__(self):
        self.n = 0
        self.numbers: dict[str, str] = {}  # what you type -> button id

    async def send(self, text, buttons=None):
        self.n += 1
        print(f"\n🤖 {text}")
        for label, data in buttons or []:
            key = str(len(self.numbers) + 1)
            self.numbers[key] = data
            print(f"   [{key}] {label}")
        return str(self.n)

    async def clear_buttons(self, message_id):
        pass

    async def typing(self):
        pass

    async def send_file(self, path, caption=""):
        print(f"\n📎 {caption} (file: {path}, deleted after sending)")


async def main():
    settings = C.Settings.from_env()
    settings.data_dir = C.ROOT / "data-terminal"
    settings.state_root = C.ROOT / "agent_state-terminal"
    store = Store(settings.data_dir)
    transport = TerminalTransport()
    agent = AgentProcess(Path(settings.agents_root), settings.agent, settings.state_root)
    harness = Harness(settings, transport, make_calendar(settings.calendar, store.calendar_dir, settings.timezone),
                      agent, store)
    await harness.start()
    print(f"Agent: {agent.version}. Type /start. Ctrl-D quits.")

    async def clock():
        while True:
            await asyncio.sleep(5)
            await harness.tick()
    ticker = asyncio.create_task(clock())
    loop = asyncio.get_running_loop()
    try:
        while True:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            if line in transport.numbers:
                await harness.on_button(transport.numbers[line])
            elif line.startswith("/"):
                cmd, _, args = line[1:].partition(" ")
                await harness.on_command(cmd.lower(), args)
            else:
                await harness.on_text(line)
    finally:
        ticker.cancel()
        await agent.stop()


if __name__ == "__main__":
    asyncio.run(main())
