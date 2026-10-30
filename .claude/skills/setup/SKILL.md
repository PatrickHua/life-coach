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

## 4. memory_repo

Memory only survives if it's committed and pushed back to GitHub.
- Make a small change (add today's date to `memory/profile.md` under "Set up on"), commit it, and push.
- If the push works, record it: `python3 scripts/mark_setup.py memory_repo "pushed <commit sha> to <branch>"`
- If the push lands on a branch other than the default branch, tell the user. Memory written on a side branch won't be seen by the next session.

## 5. schedules

Create three scheduled tasks, each starting a fresh session in this environment, with push notifications on:
- **Heartbeat**, hourly: "Life coach heartbeat. Check memory, calendar and goals. Usually do nothing. If something is worth the user's attention, propose one nudge."
- **Morning brief**, weekdays around 8:40am in the user's timezone: "Life coach morning brief. Use the morning-brief skill."
- **Weekly review**, Sunday evening: "Life coach weekly review. Use the weekly-review skill."

Then record it: `python3 scripts/mark_setup.py schedules "heartbeat, morning brief, weekly review"`

When all five are done, welcome the user, and ask what one goal they'd like help with first.
