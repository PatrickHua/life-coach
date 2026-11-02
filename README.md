# Lifecoach

A harness for finding out which AI coach actually helps people reach their goals.

The **harness** is a Telegram bot. It owns everything that has to be trustworthy: the goals you set (frozen once you lock them in), asking you whether you achieved them, the score, your calendar, and the rules about how often and how long messages can be. The **agent** is the coach, and it's swappable: any model, agent framework or self-improving system that speaks a simple JSON-lines protocol. Agents compete on one score: how many goals you achieve, and how fast.

- How it's built: [`STRUCTURE.md`](STRUCTURE.md)
- The harness ↔ agent protocol: [`protocol/PROTOCOL.md`](protocol/PROTOCOL.md)
- Writing or plugging in an agent: [`agents/README.md`](agents/README.md)

This version ships with a **mock agent** that doesn't coach. It responds to keywords so you can test every part of the harness.

---

## Test it: step by step

You need Python 3.10 or newer and a Telegram account. Allow about 15 minutes.

### 1. Install

```bash
git clone -b harness-design https://github.com/PatrickHua/life-coach.git
```

```bash
cd life-coach
```

```bash
python3 -m venv .venv && source .venv/bin/activate
```

```bash
pip install -r requirements.txt
```

On Windows, activate with `.venv\Scripts\activate` instead.

### 2. Run the tests

```bash
python -m pytest -q
```

You should see `41 passed`. If anything fails, stop here and send me the output.

### 3. Optional: try it in your terminal first

```bash
python -m tools.fake_user
```

Type `/start`, then `/goal`, and follow along. Buttons show as numbers; type the number to tap one. Ctrl-D quits. This uses its own data folder, so it doesn't affect the Telegram bot.

### 4. Create your Telegram bot

1. In Telegram, open a chat with **@BotFather** and send `/newbot`.
2. Pick a name (e.g. "My Lifecoach") and a username ending in `bot`.
3. BotFather replies with a token like `123456789:AAH...`. Keep it secret.

### 5. Configure

```bash
cp .env.example .env
```

Open `.env` and set:

- `TELEGRAM_BOT_TOKEN=` the token from BotFather
- `TIMEZONE=` your timezone, e.g. `America/Los_Angeles` or `Europe/London`
- Leave `ALLOWED_USER_ID` empty for now.

If you'll test late at night, move the quiet hours (e.g. `QUIET_START=03:00`, `QUIET_END=04:00`), or reminders will be held back.

### 6. Start the bot and lock it to you

```bash
python -m harness.main
```

Message your bot anything. It replies with your user ID. Put it in `.env` as `ALLOWED_USER_ID=...`, stop the bot (Ctrl-C), and start it again. From now on it answers only you.

### 7. Walk through the checklist

Each row says what to send and what should happen. If something doesn't match, note the step number.

| # | You send | What should happen |
|---|---|---|
| 1 | `/start` | Four short messages: hi, calendar status, timezone and quiet hours, "set your first goal". |
| 2 | `/goal`, then answer the questions | Goal → what "done" means → deadline buttons → proof buttons → a summary with **Lock it in**. Tap it. You get "🔒 Locked in", then the mock says "Got your goal…". |
| 3 | `hello`, then `hello again` | "You said: hello (message #1 I remember)", then #2. The agent keeps its own memory. |
| 4 | `buttons` | Three colour buttons. Tap one: "You picked …". The buttons disappear after the tap. |
| 5 | `help` | One short message with a **More ▾** button. Each tap shows the next page. |
| 6 | `long` | One short message plus **More ▾**, never a wall of text. (The mock sent something too long; the harness bounced it, then split it.) |
| 7 | `/log` | Shows `rejected send_message too_long` and `auto_split`. |
| 8 | `remind me` | "OK, I'll ping you around HH:MM". About a minute later: "⏰ Reminder…". |
| 9 | `remind me` again | A confirmation, but **no second reminder**: messages the agent starts on its own must be 2 hours apart. `/log` shows `min_gap`. |
| 10 | `I did it` | The **harness** asks "Goal check: … Did you achieve it?" with three buttons. Tap **⏳ Not yet**. The mock reports `not_yet`. |
| 11 | `I did it` again | The mock says the harness won't ask yet (`verify_too_soon`). Agents can ask at most once every 3 days. |
| 12 | `/done` | You can always ask yourself. The same question appears. Tap **✅ Achieved**. You get "✅ Logged as achieved". |
| 13 | `/goals` | Your goal, marked closed and ✅. |
| 14 | `/why` | The reason behind the coach's last message. |
| 15 | `/pause`, then `/resume` | "Paused…", then "Welcome back!". While paused, the coach can reply but can't start conversations. |
| 16 | `crash`, then `hi` | "Sorry, I hit a snag…", then `hi` is answered normally. The harness restarted the agent. |
| 17 | `slow` | After about 60 seconds: "Sorry, I hit a snag…". |
| 18 | `/export` | You receive a zip of all your data. |
| 19 | Stop the bot, start it again, send `/goals` | Everything is still there. |
| 20 | `/forget`, then **Delete everything** | All goals and memory are deleted. `/start` begins fresh. |

When you're done, run `python -m tools.score` to see the score table, then tell me what didn't match, or what felt wrong.

---

## Connect Google Calendar (optional)

The harness reads your calendars and, if the agent proposes an event and you tap ✅, adds it to a separate calendar called **Coach**. Google itself prevents it from changing any of your own events: it only asks for read access, plus access to calendars it creates.

1. Go to [console.cloud.google.com](https://console.cloud.google.com), create a project, and enable the **Google Calendar API**.
2. Under **Google Auth Platform** (or "OAuth consent screen"), choose **External**, fill in the app name and your email, and add yourself as a **test user**.
3. Under **Clients** (or "Credentials"), create an **OAuth client** of type **Desktop app**. Download the JSON and save it in this folder as `credentials.json`.
4. In `.env`, set `CALENDAR=google`.
5. Sign in once:

   ```bash
   python -m harness.calendar_login
   ```

   A browser opens. Approve access (Google warns that the app is unverified; that's expected for your own project).
6. Restart the bot. `/start` now says the calendar is connected.

Then test: send `calendar` (the mock lists today's events), and `propose` (the harness asks to add "Mock run" tomorrow at 18:00; tap **✅ Add**, check it appears in the Coach calendar, then send `/undo`).

While your Google project is in testing mode, Google expires the sign-in after 7 days; run `calendar_login` again when that happens.

## Try a real LLM coach

The `openai_compat` agent works with any OpenAI-compatible endpoint. In `.env`:

```
AGENT=openai_compat
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=your-key
LLM_MODEL=the-model-name-your-provider-uses
```

`LLM_BASE_URL` can also be `https://api.openai.com/v1`, a local vLLM server (`http://localhost:8000/v1`) or Ollama (`http://localhost:11434/v1`). Restart the bot. Goals stay attached to the agent version they started with, so scores never mix.

## Commands

`/start` · `/goal` set a goal · `/goals` · `/done` check off a goal · `/pause` · `/resume` · `/why` · `/undo` remove the last calendar event you added · `/bad` flag the coach's last message · `/log` recent rejections and errors · `/export` · `/forget` delete everything · `/help`

These are handled by the harness and work even if the agent is broken.

## Where things live

- `data/`: your goals, logs, outcomes and calendar token. Gitignored. Delete it to start over.
- `agent_state/`: each agent version's private memory.
- `bot.log`: the bot's log, if something goes wrong.
