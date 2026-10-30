---
name: morning-brief
description: Write the user's morning brief - today's calendar, goal steps due, and at most one suggestion. Use when the morning scheduled task fires or the user asks for today's plan.
---

# Morning brief

1. Read today's calendar, active goals in `memory/goals/`, the last 3 days of `memory/mood.jsonl`, and `memory/playbook.md`.
2. Write a brief of at most 5 lines:
   - the shape of the day (busy, light, a gap worth using)
   - the one goal step that matters most today, tied to the user's own "when X, I'll do Y" plan if there is one
   - at most one suggestion (a work block, a person to reach out to, something fun)
3. If mood was low recently, keep it lighter and drop goal pressure.
4. Send it as one push notification (the gate may hold it), or as a short page if there's more worth showing.
