# Design notes

## The idea

A coach that reaches out first, but rarely and at good moments. It knows your calendar and inbox, learns what you're like, keeps an honest record of where your time goes, and helps you finish what you set out to do.

## Principles

1. **One agent, many skills.** Skills are how-to guides loaded when a job comes up. No graph of agents.
2. **The model proposes, code decides.** Judgment (what to say, which skill, is this email important) lives in Markdown. Anything that must always hold (quiet hours, caps, setup order, never send email) lives in scripts run by hooks, or in permission rules.
3. **Silent by default.** Every wake-up may end with no message. The gate in `scripts/gate.py` has the final say.
4. **The coach never grades itself.** A separate subagent with fresh context verifies goals against evidence agreed up front.
5. **Memory is yours.** Plain files you can read and edit. Facts get end dates instead of being overwritten.
6. **Keep the harness thin.** Rules that only patch model weaknesses should be deleted as models improve. Safety limits stay.

## Model or code?

Ask: if the model gets this wrong once, what happens?

| Mild awkwardness, so Markdown | Real harm or broken state, so code |
|---|---|
| which skill fits | quiet hours, daily cap, cooldown |
| how to phrase a nudge | setup order |
| whether an email matters | never send email or delete events |
| whether the user seems stressed | deadline reached, so verify |

## Goal lifecycle

Set, then contract ("done means..."), plan (with "when X, I'll do Y"), coach, verify (subagent), retro (subagent), playbook.

The coach improves by updating `memory/playbook.md` with counts, and by proposing skill edits for you to approve. It never edits its own skills.

## Time log

The calendar holds plans; `memory/timelog.jsonl` holds what happened. The coach guesses from evidence (commits, emails, docs) and asks you to confirm, at most twice a day, at natural moments. Confirmed blocks can be mirrored to a separate "Coach log" Google Calendar.

## What's code today

| Script | Hook | Job |
|---|---|---|
| `check_setup.py` | SessionStart | detect cloud, print setup status |
| `gate.py` | PreToolUse | block scheduling before setup; enforce quiet hours, daily cap, cooldown; log nudges |
| `mark_reply.py` | UserPromptSubmit | mark nudges as answered when you reply in that session |
| `mark_setup.py` | run by the model | record a setup step after testing it |

## Open questions

- Do scheduled-task sessions push memory to the default branch, or to a side branch the next session won't see?
- Can scheduled-task sessions publish artifacts and send files, or only push notifications?
- Is hourly the shortest heartbeat this account allows?
- Two-way chat (Telegram) and live email or calendar events need an always-on service; out of scope for now.
