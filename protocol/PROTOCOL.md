# Harness ↔ agent protocol

The agent is any program. The harness starts it once as a subprocess and they exchange **JSON lines**: one JSON object per line, harness → agent on the agent's stdin, agent → harness on its stdout. Anything the agent prints to stderr goes to a log and is otherwise ignored.

- Working directory: `agent_state/<name>@<version>/`, the agent's only writable folder.
- Network: only the hosts listed in the agent's `manifest.json`.
- Schemas: `events.schema.json` (harness → agent), `actions.schema.json` (agent → harness). Anything that doesn't validate is rejected.

## Turns

Every event starts a **turn**. The agent answers with zero or more actions and ends the turn with `done`:

```
harness → {"type":"user_message","id":"e42","ts":"…","context":{…},"text":"ran today!"}
agent   → {"type":"send_message","text":"Nice, that's 2/3 this week 🏃","buttons":["👍"],"why":"acknowledge progress"}
agent   → {"type":"done","event_id":"e42"}
```

- The harness sends one event at a time and waits for `done` before sending the next.
- A turn must end within **60 seconds** (`TURN_TIMEOUT`). Time spent waiting on the harness for calendar data doesn't count.
- If the turn times out or the agent crashes, the harness logs it against the agent, restarts the agent once, and falls back to `agents/baseline` if it fails again.

### Requests inside a turn

Some actions ask the harness for something. The harness answers on stdin **before** the next event, matched by `req_id`:

```
agent   → {"type":"get_calendar","req_id":"r1","start":"2026-11-04T00:00","end":"2026-11-05T00:00"}
harness → {"type":"calendar","req_id":"r1","events":[{"start":"…","end":"…","title":"Standup","busy":true,"coach":false}]}
```

## Context

Every event carries the same `context` object, so every agent gets the basics for free:

```json
{
  "now": "2026-11-04T08:30:00+01:00",
  "timezone": "Europe/Berlin",
  "quiet_hours": {"start": "22:00", "end": "08:00"},
  "in_quiet_hours": false,
  "messages_left_today": 2,
  "awaiting_reply": false,
  "paused": false,
  "contracts": [
    {"id": "c_9f3a…", "goal": "Run 3x a week", "done_means": "12 runs logged",
     "deadline": "2026-11-29", "evidence": "self_report", "status": "active"}
  ]
}
```

Contracts are read-only copies. Changing them does nothing.

## Events (harness → agent)

| Type | Fields | When |
|---|---|---|
| `start` | `agent_version` | agent process started |
| `contract_assigned` | `contract` | a new frozen contract is given to this agent |
| `verification_result` | `contract_id`, `answer` | the user answered a verification request: `achieved`, `not_yet` or `gave_up` |
| `contract_closed` | `contract_id`, `achieved`, `days` | the outcome is final |
| `user_message` | `text`, `reply_to?` | the user wrote something |
| `button_tap` | `message_id`, `choice` | the user tapped one of the agent's buttons |
| `wakeup` | `wakeup_id`, `note` | a scheduled wakeup fired |
| `calendar` | `req_id`, `events` | answer to `get_calendar` |
| `proposal_result` | `proposal_id`, `accepted` | the user answered a `propose_event` |
| `message_sent` | `req_id`, `message_id` | a `send_message` was delivered |
| `rejected` | `req_id?`, `action`, `reason`, `detail` | the harness refused an action |
| `user_feedback` | `message_id`, `kind` | the user reacted 👎 or tapped "too pushy" |

## Actions (agent → harness)

| Type | Fields | Notes |
|---|---|---|
| `send_message` | `text`, `more?`, `buttons?`, `why`, `req_id?` | see Message rules |
| `schedule_wakeup` | `at`, `note`, `wakeup_id?` | `at` must be in the future |
| `cancel_wakeup` | `wakeup_id` | |
| `get_calendar` | `req_id`, `start`, `end` | max range 31 days |
| `propose_event` | `req_id`, `title`, `start`, `end`, `why` | the harness asks the user; answer comes as `proposal_result` |
| `request_verification` | `contract_id`, `why` | the harness asks the user whether the goal is achieved; see Verification |
| `flag` | `kind`, `detail?` | `kind`: `crisis`, `user_distress`, `bug` |
| `done` | `event_id` | ends the turn |

## Message rules

Enforced by `harness/limits.py`. Every value is in `harness/config.py`.

| Rule | Limit |
|---|---|
| `text` length | ≤ 280 characters |
| `more` | ≤ 5 pages, each ≤ 280 characters |
| `buttons` | ≤ 4, each label ≤ 20 characters |
| `why` | required, ≤ 140 characters; shown to the user by `/why` |
| Formatting | no headings, no tables; other Markdown is stripped |
| Daily cap | ≤ 3 messages the agent starts on its own per local day |
| Minimum gap | ≥ 2 hours between messages the agent starts |
| Double-texting | while `awaiting_reply`, at most 1 follow-up message |
| Duplicates | no identical `text` within 24 hours |
| Quiet hours | messages the agent starts are rejected |

A message is a **reply** if it's sent during a turn started by `user_message` or `button_tap`. Replies don't count toward the daily cap, minimum gap or double-texting, and are allowed in quiet hours. Every other message is one the agent **starts on its own** (during `wakeup`, `contract_assigned`, etc.).

### Overview first, details on request

Long content goes in `more`. The harness sends `text` with an extra **[More ▾]** button; each tap shows the next page as its own short message, with no agent involved.

```json
{"type":"send_message",
 "text":"This week: 2/3 runs done, 1 left Sat 🏃",
 "more":["Mon ✅ 30 min, Wed ✅ 25 min.", "Idea for next week: …"],
 "buttons":["👍","Move Sat"],
 "why":"weekly progress"}
```

### When a message breaks the rules

1. The harness rejects it with `rejected` (e.g. `reason: "too_long"`, `detail: "640/280, use more"`). The agent may retry once in the same turn.
2. If the retry is also too long, the harness cuts `text` at a sentence boundary and moves the rest into `more`.
3. Any other rule broken twice in one turn: the message is dropped.

## Calendar rules

- The harness holds the Google tokens. The agent never sees them.
- `get_calendar` returns events from the user's calendars, read-only. `coach: true` marks events the coach created.
- `propose_event` never writes directly. The harness shows its own confirmation, *"Add 'Run' Wed 6–7pm?"* **[✅ Add] [❌ No]**, and creates the event only on ✅, on the separate "Coach" calendar.
- The agent can't move or delete any event. `/undo` lets the user remove the last event they confirmed.
- Events with `coach: true` never count as evidence for a goal.

## Verification

The **agent decides when** to ask whether a goal is achieved. The **user gives the answer**, and that answer is the score. The agent never words the question and never sees anything but the result.

1. The agent sends `request_verification` with a `contract_id` and a `why` (e.g. *"user said they finished the last run"*).
2. The harness asks the user in its own fixed wording, not the agent's:
   > Goal check: **Run 3x a week** (done means: 12 runs logged). Did you achieve it?
   > **[✅ Achieved] [⏳ Not yet] [❌ Gave up]**

   If the contract asks for a link, file or witness, the harness collects it after ✅, again in its own flow.
3. The agent receives `verification_result`:
   - `achieved` → the contract closes as achieved. `days` = days from contract start to this answer.
   - `not_yet` → nothing changes; the contract stays active.
   - `gave_up` → the contract closes as not achieved.
4. On close, the agent receives `contract_closed`. The outcome is final.

**Rules** (in `harness/limits.py`):

| Rule | Limit |
|---|---|
| Requests per contract | ≤ 1 per 3 days, so the agent can't keep asking until the user says yes |
| Pending request | only one at a time; a new one is rejected until the user answers |
| Quiet hours, pause | requests are rejected, like messages the agent starts |
| Daily cap | a request counts as one message the agent starts |
| Unanswered request | expires after 48 hours and counts as `not_yet` |

**Backstops:**
- **Deadline:** if the contract is still open at the end of its deadline day, the harness asks the same question itself, with **[✅ Achieved] [❌ Not achieved]** only. An unanswered deadline question closes the contract as not achieved after 72 hours.
- **The user can always ask:** `/done` starts the same verification flow, so a finished goal never waits for the agent.

**Why the agent can't game it:** it chooses only *when* to ask. It can't phrase the question, add buttons to it, see evidence, or change the deadline. Asking early costs it a rate-limited request and earns nothing unless the user answers ✅.

## Harness-only commands

Handled by the harness, never passed to the agent, and working even if the agent is down: `/start`, `/pause`, `/resume`, `/stop`, `/why`, `/undo`, `/goals`, `/export`, `/forget`, `/goal` (the fixed contract form), `/done` (start verification).

## Buttons

- Buttons are removed after one tap.
- Buttons expire after 12 hours. Tapping an expired one gets *"That one's old, here's where we are now"* and is sent to the agent as a `user_message` with no choice attached.
- Confirmation buttons for side effects (calendar writes) are always drawn by the harness, never by the agent.

## Safety

- If a user message matches the harness's crisis keywords, or the agent sends `flag` with `kind: "crisis"`, the harness sends a fixed safe message with crisis resources and pauses coaching until the user sends `/resume`.
- During a pause, the agent receives no `wakeup` events, and `context.paused` is `true`.

## Rejection reasons

`invalid_schema`, `too_long`, `too_many_pages`, `too_many_buttons`, `button_too_long`, `missing_why`, `over_daily_cap`, `min_gap`, `double_text`, `duplicate`, `quiet_hours`, `paused`, `verify_too_soon`, `verify_pending`, `unknown_contract`, `contract_closed`, `calendar_range`, `wakeup_in_past`, `unknown_wakeup`, `turn_timeout`.
