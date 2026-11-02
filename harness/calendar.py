"""Google Calendar, owned by the harness. The agent never sees tokens.

Scopes: read-only access to the user's calendars, plus full access only to calendars this app
creates (the separate "Coach" calendar). Google itself stops the app touching the user's own events.
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.app.created",
]
COACH_CALENDAR = "Coach"


class NoCalendar:
    connected = False
    status = "Calendar is off (CALENDAR=none in .env)."

    async def list_events(self, start: datetime, end: datetime) -> list[dict]:
        return []

    async def create_event(self, title: str, start: datetime, end: datetime) -> str:
        raise RuntimeError("calendar not connected")

    async def delete_event(self, event_id: str) -> None:
        raise RuntimeError("calendar not connected")


class GoogleCalendar:
    def __init__(self, calendar_dir: Path, timezone: str):
        self.token_path = Path(calendar_dir) / "token.json"
        self.meta_path = Path(calendar_dir) / "coach_calendar.json"
        self.timezone = timezone
        self._service = None

    @property
    def connected(self) -> bool:
        return self.token_path.exists()

    @property
    def status(self) -> str:
        if self.connected:
            return "✅ Google Calendar is connected."
        return "Google Calendar isn't connected yet. On your computer, run: python -m harness.calendar_login"

    def _svc(self):
        if self._service is None:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
            if not creds.valid and creds.refresh_token:
                creds.refresh(Request())
                self.token_path.write_text(creds.to_json())
            self._service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        return self._service

    def _coach_id(self) -> str:
        if self.meta_path.exists():
            return json.loads(self.meta_path.read_text())["id"]
        cal = self._svc().calendars().insert(body={"summary": COACH_CALENDAR, "timeZone": self.timezone}).execute()
        self.meta_path.write_text(json.dumps({"id": cal["id"]}))
        return cal["id"]

    def _list(self, start: datetime, end: datetime) -> list[dict]:
        svc = self._svc()
        coach_id = json.loads(self.meta_path.read_text())["id"] if self.meta_path.exists() else None
        out = []
        for cal in svc.calendarList().list().execute().get("items", []):
            if cal.get("selected") is False and cal["id"] != coach_id:
                continue
            items = svc.events().list(calendarId=cal["id"], timeMin=start.isoformat(), timeMax=end.isoformat(),
                                      singleEvents=True, orderBy="startTime", maxResults=250).execute()
            for ev in items.get("items", []):
                s, e = ev.get("start", {}), ev.get("end", {})
                out.append({
                    "start": s.get("dateTime") or s.get("date") + "T00:00:00+00:00",
                    "end": e.get("dateTime") or e.get("date") + "T00:00:00+00:00",
                    "title": ev.get("summary", "(no title)"),
                    "busy": ev.get("transparency") != "transparent",
                    "coach": cal["id"] == coach_id,
                })
        return sorted(out, key=lambda ev: ev["start"])

    def _create(self, title: str, start: datetime, end: datetime) -> str:
        body = {"summary": title, "start": {"dateTime": start.isoformat()}, "end": {"dateTime": end.isoformat()}}
        return self._svc().events().insert(calendarId=self._coach_id(), body=body).execute()["id"]

    def _delete(self, event_id: str) -> None:
        self._svc().events().delete(calendarId=self._coach_id(), eventId=event_id).execute()

    async def list_events(self, start, end):
        return await asyncio.to_thread(self._list, start, end)

    async def create_event(self, title, start, end):
        return await asyncio.to_thread(self._create, title, start, end)

    async def delete_event(self, event_id):
        await asyncio.to_thread(self._delete, event_id)


def make_calendar(kind: str, calendar_dir: Path, timezone: str):
    return GoogleCalendar(calendar_dir, timezone) if kind == "google" else NoCalendar()
