# Lifecoach: project structure

One rule shapes everything: **the harness is trusted, the agent is not.** They live in separate folders, run as separate processes, and talk only through the JSON-lines protocol in `protocol/`.

```
lifecoach/
├── README.md
├── STRUCTURE.md                # this file
├── pyproject.toml
├── .env.example                # TELEGRAM_BOT_TOKEN, ALLOWED_USER_ID, GOOGLE_CLIENT_ID,
│                               # GOOGLE_CLIENT_SECRET, TOKEN_KEY, AGENT
│
├── harness/                    # TRUSTED. The improving system never edits this.
│   ├── main.py                 # entry point: starts the bot, loads the agent, runs the clock
│   ├── config.py               # all limits and timeouts in one place
│   │
│   ├── telegram_io.py          # Telegram in/out; the only code that talks to Telegram
│   ├── onboarding.py           # /start flow: connect calendar → timezone/quiet hours → first contract
│   ├── commands.py             # /pause /resume /stop /why /undo /goals /export /forget
│   ├── buttons.py              # button rendering, one-tap removal, expiry, [More ▾] paging
│   │
│   ├── calendar.py             # Google OAuth, token storage, read queries, "Coach" calendar writes;
│   │                           # refuses to touch events it didn't create
│   ├── proposals.py            # turns agent proposals into harness-drawn confirm buttons; /undo
│   │
│   ├── contract.py             # fixed goal form; create, freeze (hash), load; no edits after freeze
│   ├── verifier.py             # asks "did you achieve it?" in fixed wording, when the agent requests it,
│   │                           # on /done, or at the deadline; collects evidence outside the agent's chat;
│   │                           # coach-created calendar events never count as evidence
│   ├── scorer.py               # computes scores and guardrail flags from the event log
│   │
│   ├── relay.py                # event → agent → actions; validates every action against the schema
│   ├── limits.py               # message length, buttons, daily cap, quiet hours, min gap,
│   │                           # double-texting, duplicates; returns accept / reject(reason)
│   ├── safety.py               # crisis keywords + agent flags → fixed safe reply, pause coaching
│   ├── agent_process.py        # runs the agent as a subprocess; timeouts; crash → retry → baseline
│   └── store.py                # append-only writes to data/; the only code that writes there
│
├── protocol/                   # THE CONTRACT BETWEEN THE TWO SIDES
│   ├── PROTOCOL.md             # events, actions, limits, errors, examples
│   ├── events.schema.json      # harness → agent
│   └── actions.schema.json     # agent → harness
│
├── agents/                     # UNTRUSTED. The improving system works here.
│   ├── baseline/               # dumb reminder bot: the floor every agent should beat,
│   │   ├── agent.py            # and the fallback when an agent crashes
│   │   └── manifest.json       # {"name", "command", "network": []}
│   └── claude_coach/           # first real agent; its insides are its own business
│       ├── agent.py
│       ├── manifest.json       # e.g. "network": ["api.anthropic.com"]
│       └── prompts/
│
├── data/                       # HARNESS-OWNED. Gitignored. The agent has no access.
│   ├── contracts/              # one frozen JSON per goal, named by its hash
│   ├── events.jsonl            # every event, action and rejection, append-only
│   ├── evidence/               # files and links submitted at verification
│   ├── verifications.jsonl     # every request (who asked, why) and the user's answer
│   ├── calendar/               # encrypted Google token; ids of events the coach created
│   └── scores.csv              # agent version, contract, achieved, days, guardrail flags
│
├── agent_state/                # one private folder per agent version: the agent's only writable space
│   └── claude_coach@a1b2c3/
│
├── tools/
│   ├── score.py                # print the score per agent version
│   ├── replay.py               # replay events.jsonl against an agent offline
│   └── fake_user.py            # chat with an agent in the terminal, no Telegram
│
└── tests/
    ├── test_contract_frozen.py # editing a frozen contract fails
    ├── test_limits.py          # length, buttons, cap, quiet hours, gap, double-text, duplicates
    ├── test_more_paging.py     # long content becomes [More ▾] pages
    ├── test_calendar_guard.py  # can't move/delete user events; coach events aren't evidence
    ├── test_proposals.py       # nothing is written without the user's ✅
    ├── test_verification.py    # rate limit, one pending request, expiry, deadline backstop, /done
    ├── test_commands.py        # /pause /stop work even when the agent is dead
    ├── test_agent_isolation.py # agent can't read data/ or write outside its state folder
    └── test_scorer.py
```

## Who can write where

| Folder | Harness | Agent | Improving system |
|---|---|---|---|
| `harness/`, `protocol/`, `tests/` | — | ❌ | ❌ (read only) |
| `data/` | ✅ append only | ❌ | ❌ (reads `scores.csv` only) |
| `agents/<name>/` | ❌ | ❌ | ✅ |
| `agent_state/<version>/` | ❌ | ✅ | ❌ |

## Agent versions

An agent's version is the hash of its folder under `agents/`. Changing any file creates a new version with its own `agent_state/` folder and its own scores. A contract stays with the version it started with.

## Build order

1. `store`, `contract`, `telegram_io`, `commands`: a bot that can freeze a goal.
2. `calendar`, `onboarding`: connect Google Calendar first.
3. `relay`, `limits`, `buttons`, `agent_process`, plus `agents/baseline`: end-to-end with the dumb agent.
4. `verifier`, `scorer`: the score exists.
5. `proposals`, `safety`, then `agents/claude_coach`.
