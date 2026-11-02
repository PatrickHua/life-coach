# Writing an agent

An agent is **any program that reads JSON lines on stdin and writes JSON lines on stdout**. That's the whole interface, so you can plug in anything: a frontier model's API, an open-source model on vLLM or Ollama, an agent framework, a CLI coding agent, or a self-improving system that rewrites its own code.

The full protocol is in [`../protocol/PROTOCOL.md`](../protocol/PROTOCOL.md). The short version:

1. The harness sends one **event** (a user message, a button tap, a wakeup, a new goal…).
2. You write zero or more **actions**. After each one, read exactly one reply line (`message_sent`, `accepted`, `calendar` or `rejected`).
3. Write `{"type": "done", "event_id": "<the event's id>"}` to end the turn, within 60 seconds.

## Folder layout

```
agents/my_agent/
├── manifest.json
└── ...anything you like
```

`manifest.json`:

```json
{
  "name": "my_agent",
  "command": ["python3", "{agent_dir}/agent.py"],
  "env": ["MY_API_KEY"]
}
```

- `command` is run as a subprocess. `{agent_dir}` is replaced by this folder's path. Any language works: `["node", "{agent_dir}/index.js"]`, `["{agent_dir}/my-binary"]`, `["uv", "run", "{agent_dir}/agent.py"]`.
- `env` lists the environment variables the agent may see. Nothing else is passed through; in particular the harness's Telegram token and Google credentials never are.
- The working directory is the agent's own private state folder, `agent_state/<name>@<version>/`. Keep memory there, in whatever format you like.
- The **version** is a hash of every file in this folder. Change anything and you get a new version, with a fresh state folder and its own scores.

To run it, set `AGENT=my_agent` in `.env`. `AGENT` can also be a path to a folder outside this repo, e.g. `AGENT=/home/me/rsi-workspace/coach`, so a self-improving system can work in its own checkout without being able to touch the harness.

## Examples

| Agent | What it shows |
|---|---|
| [`mock/`](mock/) | Every protocol feature, driven by keywords. No model. Use it to test the harness. |
| [`openai_compat/`](openai_compat/) | A real LLM coach in ~120 lines of standard-library Python, for any OpenAI-compatible endpoint. |

### Wrapping other systems

- **Hosted models** (OpenAI, OpenRouter, Anthropic's OpenAI-compatible endpoint, Groq…): use `openai_compat` and set `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`.
- **Your own model** on vLLM (`vllm serve <model>` → `http://localhost:8000/v1`) or Ollama (`http://localhost:11434/v1`): same agent, just point `LLM_BASE_URL` at it.
- **Provider SDKs or agent frameworks** (Anthropic SDK, OpenAI Agents SDK, LangGraph…): write a small loop that reads an event, runs your agent, writes actions, writes `done`. Expose the harness actions as the agent's tools.
- **CLI agents** (Claude Code, opencode…): call them headless per event, e.g. `claude -p "<event JSON>" --output-format json`, and turn their output into actions.
- **Self-improving systems**: point `AGENT` at the folder they edit. Read scores with `python -m tools.score`. They can't edit `harness/`, `protocol/` or `data/`, which is where the score comes from.

## What the agent never controls

Goal contracts, the wording of "did you achieve it?", evidence, deadlines, the scores, message limits, quiet hours, calendar writes (only proposals the user confirms), and the harness commands like `/pause`. See the "Who can write where" table in [`../STRUCTURE.md`](../STRUCTURE.md).
