---
name: setup
description: Walk the user through first-time setup of the life coach, one step at a time. Use when the SETUP line says setup is incomplete, or when the user asks to set up or re-check the coach.
---

# Setup

Setup has five steps, in this order. Work only on the first one that isn't done, then stop and tell the user what's next. Keep each message short and friendly.

## 1. cloud

Detected automatically. If it isn't done, the user is running Claude Code on their own computer. Explain that the coach needs to run while their computer is off, so it lives in Claude Code on the web. Tell them to open claude.ai/code, start a session with this repository selected, and say "set up my coach".

## 2. calendar

Call the Google Calendar `list_calendars` tool.
- If it fails or isn't available, ask the user to connect Google Calendar in claude.ai settings under Connectors, then try again.
- If it works, ask whether they want a separate calendar for the coach's time log. If yes, they create a calendar named "Coach log" in Google Calendar (you can't create calendars), then you look up its id and save it as `coach_calendar_id` in `memory/config.json`. If no, that's fine; the log stays in `memory/timelog.jsonl`.
- Ask for their timezone if `memory/config.json` doesn't have the right one.
- Record it: `python3 scripts/mark_setup.py calendar "<calendar count> calendars found"`

## 3. gmail

Call the Gmail `search_threads` tool with a narrow query, such as messages from the last day.
- If it fails, ask the user to connect Gmail under Connectors.
- Tell them plainly: the coach reads email to find what matters and can draft replies, but it can never send.
- Record it: `python3 scripts/mark_setup.py gmail "search returned <n> threads"`

## 4. home

The coach lives in this one session, and its memory lives in `memory/` on this machine. Nothing is pushed to GitHub or copied elsewhere unless the user asks for an export.
- Write today's date under "Set up on" in `memory/profile.md`.
- Tell the user plainly: this session is the coach's home. Keep it, don't archive it, and talk to the coach here. A new session starts on a fresh machine without this memory.
- Record it: `python3 scripts/mark_setup.py home "session $CLAUDE_CODE_SESSION_ID"`

## 5. schedules

Create three scheduled tasks that fire into **this session** (not a fresh session each time), so they see the same memory. Start each prompt with a `[coach:...]` tag; the reply tracker uses it to tell scheduled wake-ups from the user's own messages.
- **Heartbeat**, hourly: "[coach:heartbeat] Check memory, calendar and goals. Usually do nothing. If something is worth the user's attention, propose one nudge."
- **Morning brief**, weekdays around 8:40am in the user's timezone: "[coach:morning] Use the morning-brief skill."
- **Weekly review**, Sunday evening: "[coach:weekly] Use the weekly-review skill."

Then record it: `python3 scripts/mark_setup.py schedules "heartbeat, morning brief, weekly review"`

When all five are done, welcome the user, and ask what one goal they'd like help with first.
