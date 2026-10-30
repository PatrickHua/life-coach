"""Shared helpers for the coach's hook scripts."""
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path(__file__).resolve().parent.parent))
MEMORY = ROOT / "memory"

SETUP_STEPS = ["cloud", "calendar", "gmail", "memory_repo", "schedules"]


def load_json(name, default):
    try:
        return json.loads((MEMORY / name).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(name, data):
    (MEMORY / name).write_text(json.dumps(data, indent=2) + "\n")


def read_jsonl(name):
    path = MEMORY / name
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def write_jsonl(name, rows):
    (MEMORY / name).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def config():
    return load_json("config.json", {})


def now():
    return datetime.now(ZoneInfo(config().get("timezone", "UTC")))


def setup_state():
    """Cloud is always checked live; a saved value could come from another machine."""
    state = load_json("setup.json", {})
    done = {step: bool(state.get(step)) for step in SETUP_STEPS}
    done["cloud"] = is_cloud()
    return done


def is_cloud():
    return os.environ.get("CLAUDE_CODE_REMOTE") == "true"
