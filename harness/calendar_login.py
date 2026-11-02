"""One-time Google sign-in, run on your computer: python -m harness.calendar_login"""
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from .calendar import SCOPES
from .config import Settings
from .store import Store


def main() -> None:
    settings = Settings.from_env()
    secret = Path(settings.google_client_secret)
    if not secret.exists():
        sys.exit(f"Can't find {secret}. Download your OAuth client file from Google Cloud (see README).")
    flow = InstalledAppFlow.from_client_secrets_file(str(secret), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    token = Store(settings.data_dir).calendar_dir / "token.json"
    token.write_text(creds.to_json())
    print(f"Connected. Token saved to {token}")


if __name__ == "__main__":
    main()
