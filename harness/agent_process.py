"""Runs an agent as a subprocess speaking JSON lines over stdin/stdout."""
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path


class AgentDied(Exception):
    pass


def agent_version(agent_dir: Path) -> str:
    """Hash of every file in the agent's folder: change any file, get a new version."""
    h = hashlib.sha256()
    for path in sorted(p for p in agent_dir.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
        h.update(str(path.relative_to(agent_dir)).encode())
        h.update(path.read_bytes())
    return h.hexdigest()[:8]


class AgentProcess:
    def __init__(self, agents_root: Path, name: str, state_root: Path):
        """`name` is a folder in agents/, or a path to an agent folder anywhere (e.g. another checkout)."""
        path = Path(name).expanduser()
        self.dir = (path if path.is_absolute() or "/" in name else Path(agents_root) / name).resolve()
        self.manifest = json.loads((self.dir / "manifest.json").read_text())
        self.name = self.dir.name
        self.version = f"{self.name}@{agent_version(self.dir)}"
        self.state_dir = Path(state_root) / self.version
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.proc: asyncio.subprocess.Process | None = None

    def _command(self) -> list[str]:
        cmd = [part.replace("{agent_dir}", str(self.dir)) for part in self.manifest["command"]]
        if cmd[0] in ("python", "python3"):
            cmd[0] = sys.executable
        return cmd

    def _env(self) -> dict:
        """A bare environment: no harness secrets, only what the manifest asks for."""
        env = {"PATH": os.environ.get("PATH", ""), "HOME": str(self.state_dir),
               "LANG": os.environ.get("LANG", "C.UTF-8"), "PYTHONUNBUFFERED": "1"}
        for key in self.manifest.get("env", []):
            if key in os.environ:
                env[key] = os.environ[key]
        return env

    async def start(self) -> None:
        stderr = open(self.state_dir.parent / f"{self.version}.stderr.log", "ab")
        self.proc = await asyncio.create_subprocess_exec(
            *self._command(), cwd=self.state_dir, env=self._env(),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=stderr,
            limit=1 << 20)

    @property
    def alive(self) -> bool:
        return self.proc is not None and self.proc.returncode is None

    async def send(self, obj: dict) -> None:
        if not self.alive:
            raise AgentDied("not running")
        try:
            self.proc.stdin.write((json.dumps(obj, ensure_ascii=False) + "\n").encode())
            await self.proc.stdin.drain()
        except (BrokenPipeError, ConnectionResetError) as e:
            raise AgentDied(str(e)) from e

    async def read(self, timeout: float) -> dict | str:
        """Next line from the agent: a dict, or the raw string if it isn't JSON."""
        line = await asyncio.wait_for(self.proc.stdout.readline(), timeout=max(timeout, 0.01))
        if not line:
            raise AgentDied("exited")
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return line.decode(errors="replace").strip()
        return obj if isinstance(obj, dict) else line.decode(errors="replace").strip()

    async def stop(self) -> None:
        if self.alive:
            self.proc.kill()
            await self.proc.wait()

    async def restart(self) -> None:
        await self.stop()
        await self.start()
