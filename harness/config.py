"""All limits and settings in one place."""
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Message rules (protocol/PROTOCOL.md, "Message rules")
MAX_TEXT = 280
MAX_PAGES = 5
MAX_BUTTONS = 4
MAX_BUTTON_LABEL = 20
MAX_WHY = 140
DAILY_CAP = 3
MIN_GAP_HOURS = 2
DUPLICATE_HOURS = 24
BUTTON_EXPIRY_HOURS = 12

# Verification
VERIFY_GAP_DAYS = 3
VERIFY_EXPIRY_HOURS = 48
DEADLINE_ANSWER_HOURS = 72

# Agent and calendar
CALENDAR_MAX_DAYS = 31
MAX_WAKEUPS = 50
TICK_SECONDS = 20


def load_dotenv(path: Path) -> None:
    """Minimal .env reader: KEY=value lines, no overriding real env vars."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass
class Settings:
    telegram_token: str = ""
    allowed_user_id: int = 0
    timezone: str = "UTC"
    quiet_start: str = "22:00"
    quiet_end: str = "08:00"
    agent: str = "mock"
    calendar: str = "none"  # "none" or "google"
    google_client_secret: str = str(ROOT / "credentials.json")
    data_dir: Path = ROOT / "data"
    state_root: Path = ROOT / "agent_state"
    agents_root: Path = ROOT / "agents"
    turn_timeout: float = 60.0

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(ROOT / ".env")
        env = os.environ.get
        return cls(
            telegram_token=env("TELEGRAM_BOT_TOKEN", ""),
            allowed_user_id=int(env("ALLOWED_USER_ID", "0") or 0),
            timezone=env("TIMEZONE", "UTC"),
            quiet_start=env("QUIET_START", "22:00"),
            quiet_end=env("QUIET_END", "08:00"),
            agent=env("AGENT", "mock"),
            calendar=env("CALENDAR", "none"),
            google_client_secret=env("GOOGLE_CLIENT_SECRET_FILE", str(ROOT / "credentials.json")),
            turn_timeout=float(env("TURN_TIMEOUT", "60")),
        )
