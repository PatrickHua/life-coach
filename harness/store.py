"""The only code that writes to data/. Logs are append-only."""
import json
import os
import shutil
from pathlib import Path


class Store:
    def __init__(self, data_dir: Path):
        self.dir = Path(data_dir)
        self.contracts_dir = self.dir / "contracts"
        self.evidence_dir = self.dir / "evidence"
        self.calendar_dir = self.dir / "calendar"
        self.events_path = self.dir / "events.jsonl"
        self.outcomes_path = self.dir / "outcomes.jsonl"
        self.verifications_path = self.dir / "verifications.jsonl"
        self.state_path = self.dir / "state.json"
        self.ensure()

    def ensure(self) -> None:
        for d in (self.dir, self.contracts_dir, self.evidence_dir, self.calendar_dir):
            d.mkdir(parents=True, exist_ok=True)

    def append(self, path: Path, record: dict) -> None:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def log(self, record: dict) -> None:
        self.append(self.events_path, record)

    def read_jsonl(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        with open(path, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    def load_state(self) -> dict | None:
        if not self.state_path.exists():
            return None
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def save_state(self, state: dict) -> None:
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.state_path)

    def wipe(self) -> None:
        """Delete everything except the Google token, so /forget doesn't disconnect the calendar."""
        for child in self.dir.iterdir():
            if child == self.calendar_dir:
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.chmod(0o644)
                child.unlink()
        self.ensure()
