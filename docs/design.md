# Design notes

## The idea

A coach that reaches out first, but rarely and at good moments. It knows your calendar and inbox, learns what you're like, keeps an honest record of where your time goes, and helps you finish what you set out to do.

## Principles

1. **One agent, many skills.** Skills are how-to guides loaded when a job comes up. No graph of agents.
2. **The model proposes, code decides.** Judgment (what to say, which skill, is this email important) lives in Markdown. Anything that must always hold (quiet hours, caps, setup order, never send email) lives in scripts run by hooks, or in permission rules.
3. **Silent by default, persistent when it matters.** Every wake-up may end with no message, and the gate in `scripts/gate.py` has the final say. An unanswered nudge only spaces out the next one (3h by default); it never mutes the coach. Only the user can pause it.
4. **The coach never grades itself.** A separate subagent with fresh context verifies goals against evidence agreed up front.
5. **Memory is yours and stays put.** Plain files you can read and edit, kept on the home session's machine. Nothing is pushed or copied elsewhere unless you ask for an export. Facts get end dates instead of being overwritten.
6. **Keep the harness thin.** Rules that only patch model weaknesses should be deleted as models improve. Safety limits stay.

## Model or code?

Ask: if the model gets this wrong once, what happens?

| Mild awkwardness, so Markdown | Real harm or broken state, so code |
|---|---|
| which skill fits | quiet hours, daily cap, retry spacing, pause |
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
| `check_setup.py` | SessionStart | create memory from templates, check for updates, detect cloud, print setup status |
| `gate.py` | PreToolUse | block scheduling before setup; enforce quiet hours, daily cap, retry spacing and pause; log nudges |
| `mark_reply.py` | UserPromptSubmit | mark nudges as answered when you reply in that session |
| `mark_setup.py` | run by the model | record a setup step after testing it |

## Updates

Code comes from GitHub; memory is created from `templates/memory/` and ignored by git. So an installed coach updates with `git pull --ff-only` and keeps everything it has learned. New memory files in the templates are added on the next run; existing ones are never replaced. If a future version needs to change the shape of existing memory, it ships a migration script that the update skill runs.

## Open questions

- How long does an idle home session keep its disk? Files survived one machine restart on 2026-10-30, but a session that is archived or reclaimed loses its memory unless you exported it.
- Can a scheduled wake-up in the home session publish artifacts and send files, or only push notifications?
- Is hourly the shortest heartbeat this account allows?
- Scheduled wake-ups can run late: on 2026-11-02 the 8:41 morning task arrived at 9:43 and the 9:17 heartbeat at 9:30. Whichever arrives first should do the morning plan, and the other should notice it's done and stay quiet.
- Two-way chat (Telegram) and live email or calendar events need an always-on service; out of scope for now.
