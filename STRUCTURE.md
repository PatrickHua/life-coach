# Lifecoach: project structure

One rule shapes everything: **the harness is trusted, the agent is not.** They live in separate folders, run as separate processes, and talk only through the JSON-lines protocol in `protocol/`.

```
lifecoach/
├── README.md                   # setup and testing
├── STRUCTURE.md                # this file
├── pyproject.toml, requirements.txt
├── .env.example                # copy to .env
│
├── harness/                    # TRUSTED. Agents and self-improving systems never edit this.
│   ├── main.py                 # entry point: python -m harness.main
│   ├── config.py               # all limits and settings in one place
│   ├── core.py                 # the harness: onboarding, goal form, commands, buttons, verification,
│   │                           # turns with the agent, the clock (wakeups, deadlines)
│   ├── limits.py               # message length, buttons, daily cap, quiet hours, min gap,
│   │                           # double-texting, duplicates, splitting long text behind [More]
│   ├── contract.py             # goal contracts: freeze (hash, read-only file), load, detect tampering
│   ├── agent_process.py        # runs the agent as a subprocess with a bare environment; versions by hash
│   ├── calendar.py             # Google Calendar: read the user's calendars, write only to a "Coach" calendar
│   ├── calendar_login.py       # one-time Google sign-in: python -m harness.calendar_login
│   ├── safety.py               # crisis keywords → fixed safe reply, coaching paused
│   ├── scorer.py               # scores per agent version, from harness-owned logs only
│   ├── store.py                # the only code that writes to data/; logs are append-only
│   └── telegram_io.py          # the only code that talks to Telegram; allowlist of one user
│
├── protocol/                   # THE CONTRACT BETWEEN THE TWO SIDES
│   ├── PROTOCOL.md             # events, actions, limits, verification, errors
│   ├── events.schema.json      # harness → agent
│   └── actions.schema.json     # agent → harness (every action is validated against this)
│
├── agents/                     # UNTRUSTED. Swap in anything that speaks the protocol.
│   ├── README.md               # how to write or wrap an agent
│   ├── mock/                   # keyword-driven test agent, no model
│   └── openai_compat/          # simple LLM coach for any OpenAI-compatible endpoint
│
├── tools/
│   ├── fake_user.py            # chat with the harness in your terminal: python -m tools.fake_user
│   └── score.py                # print scores, write data/scores.csv: python -m tools.score
│
├── tests/                      # pytest; drives the real harness with real agent subprocesses
│
├── data/                       # HARNESS-OWNED, gitignored, created on first run
│   ├── state.json              # current harness state
│   ├── events.jsonl            # every event, action, rejection and user message, append-only
│   ├── contracts/              # one frozen, read-only JSON per goal, named by its hash
│   ├── verifications.jsonl     # every "did you achieve it?" request and answer
│   ├── outcomes.jsonl          # closed goals: agent version, achieved, days
│   ├── evidence/               # links submitted at verification
│   ├── calendar/               # Google token and the Coach calendar's id
│   └── scores.csv              # written by tools/score.py
│
└── agent_state/                # gitignored; one private folder per agent version
    └── mock@1a2b3c4d/          # the agent's working directory and only writable space
```

## Who can write where

| Folder | Harness | Agent | Improving system |
|---|---|---|---|
| `harness/`, `protocol/`, `tests/` | — | ❌ | ❌ (read only) |
| `data/` | ✅ append only | ❌ | ❌ (reads scores only) |
| `agents/<name>/` | ❌ | ❌ | ✅ |
| `agent_state/<version>/` | ❌ | ✅ | ❌ |

v0 enforces this with separate processes, a bare environment and separate working directories. An agent running as the same OS user could still read `data/` if it went looking. For real isolation, run agents in a container or as a different OS user, or keep the improving system in its own checkout and point `AGENT` at it.

## Agent versions

An agent's version is the hash of every file in its folder. Changing any file creates a new version with its own `agent_state/` folder and its own scores. A goal stays with the version it was assigned to.
