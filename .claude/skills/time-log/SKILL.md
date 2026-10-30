---
name: time-log
description: Fill gaps in the record of how the user actually spent their time. Use on heartbeats after a calendar block ends, around lunch and in the evening, or when the user mentions what they did.
---

# Time log

The calendar shows plans; `memory/timelog.jsonl` records what actually happened.

## Guess first, then confirm

1. Find the unlogged gaps today between waking hours.
2. Look for evidence: commits, sent emails, edited docs, calendar events that ended, RSVPs.
3. Ask one short question that offers a guess: "Looks like you worked on eval scripts 9-12, right?" A tap to confirm beats a blank "what did you do?"
4. Batch gaps into one question. At most 2 time-log questions a day, and respect any "don't ask about..." in `memory/config.json`.
5. If the user says skip, log the gap as `"skipped": true` and move on.

## Record format

One line per block in `memory/timelog.jsonl`:

```json
{"date": "2026-10-29", "start": "09:00", "end": "12:00", "what": "eval scripts for BabyAgent", "category": "Research", "source": "confirmed", "evidence": "4 commits"}
```

`source` is `confirmed` (user said yes), `user` (user told you), or `guess` (unconfirmed; never counted in stats).

## Mirror to Google Calendar

If `coach_calendar_id` is set in `memory/config.json`, add each confirmed block as an event on that calendar. Never write to any other calendar.
