# Life Coach

A proactive life coach that runs in Claude Code on the web. It reads your calendar and email, keeps track of how you actually spend your time, helps you reach the goals you set, and checks in without being annoying.

Everything is plain files: Markdown for judgment (persona, skills, subagents), JSON for settings and memory, and a few small Python scripts for the rules that must always hold.

## Get started

1. Open [claude.ai/code](https://claude.ai/code) and start a session with this repo selected.
2. Say "set up my coach". It walks you through five steps: cloud, Google Calendar, Gmail, making this session its home, and scheduled check-ins.
3. Keep talking to the coach in that same session. Its memory lives on that session's machine and is never pushed anywhere unless you ask for an export.

## Updating

When new code is pushed here, the coach notices at the next session start and offers to update. Say "update the coach" any time. Updating pulls the new code with git; `memory/` is ignored by git, so what the coach has learned is never touched.

## How it's put together

| Piece | Where | Decided by |
|---|---|---|
| Persona and house rules | `CLAUDE.md` | the model |
| Skills: setup, morning brief, goal coaching, time log, weekly review | `.claude/skills/` | the model |
| Subagents: goal verifier, retro | `.claude/agents/` | the model, with fresh context |
| Setup check, nudge gate, reply tracking | `scripts/`, run by hooks in `.claude/settings.json` | code |
| Never send email, never delete events | `permissions.deny` in `.claude/settings.json` | Claude Code |
| Memory | `memory/`, created from `templates/memory/`, ignored by git | readable and editable by you |

See [docs/design.md](docs/design.md) for the reasoning.

## Try the rules locally

```bash
cd scripts
echo '{"tool_name":"PushNotification","tool_input":{"message":"hi"}}' | python3 gate.py; echo "exit $?"
```

Exit 2 means blocked; the reason is printed.
