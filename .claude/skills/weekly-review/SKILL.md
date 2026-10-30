---
name: weekly-review
description: Make the user's weekly review - where time went, goal progress, mood, and a checklist for next week. Use when the weekly scheduled task fires or the user asks how their week went.
---

# Weekly review

1. Gather the week: calendar events, `memory/timelog.jsonl` (confirmed blocks only), goals, mood, `memory/nudges.jsonl`.
2. Build a short page (an artifact) with:
   - hours by category, from calendar and time log, labeled separately
   - goal progress, honestly
   - 2-4 things you noticed, written as observations, not judgments
   - 3-5 suggestions for next week as a checklist
3. Ask one question: "How did this week feel, 1-5?" Log the answer in `memory/mood.jsonl`.
4. Check the nudge stats: how many sent, how many answered. If fewer than half got a reply, send fewer next week and note it in `memory/playbook.md`.
5. Send one push with the link.
