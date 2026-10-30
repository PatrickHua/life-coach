---
name: goal-coaching
description: Help the user set, plan and follow through on a goal. Use when the user states a goal, when a goal's check-in is due, or when progress signals suggest a goal is slipping.
---

# Goal coaching

## Setting a goal

Create `memory/goals/<short-name>.md` from `memory/goals/_template.md`. Before it counts as active, agree with the user on:
- **Done means**: what evidence will show it's finished (a merged PR, a file, an event, or the user's own yes/no)
- **Deadline**
- **Push level**: gentle, firm or drill sergeant
- **Plan**: 2-5 steps, and at least one "when X, I'll do Y" plan

Propose calendar blocks for the steps. Only add them after the user says yes.

## Checking in

- Look for progress evidence first (commits, files, calendar, timelog). Only ask if there's none.
- Behind schedule? Say so honestly and offer to re-plan or cut scope. Persuade with the user's own reasons, from the goal file, never with guilt.
- Log every check-in under "Progress" in the goal file.

## At the deadline

Don't decide the outcome yourself. Start the `goal-verifier` subagent with the goal file path. Then start the `retro` subagent to update the playbook.
