"""A minimal LLM coach for any OpenAI-compatible Chat Completions endpoint. Standard library only.

Env: LLM_BASE_URL (e.g. http://localhost:8000/v1 for vLLM, http://localhost:11434/v1 for Ollama,
https://openrouter.ai/api/v1), LLM_API_KEY, LLM_MODEL.
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

PROMPT = (Path(__file__).parent / "prompt.md").read_text()
HISTORY = Path("history.jsonl")  # cwd is this agent's private state folder
KEEP = 30
ACTIVE_EVENTS = {"contract_assigned", "user_message", "button_tap", "wakeup", "verification_result",
                 "proposal_result", "user_feedback"}


def write(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def read():
    line = sys.stdin.readline()
    if not line:
        sys.exit(0)
    return json.loads(line)


def log(*args):
    print(*args, file=sys.stderr, flush=True)


def history():
    if not HISTORY.exists():
        return []
    return [json.loads(line) for line in HISTORY.read_text().splitlines()[-KEEP:]]


def remember(role, content):
    with open(HISTORY, "a") as f:
        f.write(json.dumps({"role": role, "content": content}, ensure_ascii=False) + "\n")


def chat(messages):
    base = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    body = {"model": os.environ.get("LLM_MODEL", "gpt-4o-mini"), "messages": messages,
            "response_format": {"type": "json_object"}, "temperature": 0.7}
    req = urllib.request.Request(base + "/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + os.environ.get("LLM_API_KEY", "none")})
    with urllib.request.urlopen(req, timeout=45) as resp:
        content = json.loads(resp.read())["choices"][0]["message"]["content"]
    start, end = content.find("{"), content.rfind("}")  # tolerate models that wrap JSON in prose
    return json.loads(content[start:end + 1])


def handle(ev):
    if ev["type"] not in ACTIVE_EVENTS:
        return
    event_text = json.dumps(ev, ensure_ascii=False)
    try:
        decision = chat([{"role": "system", "content": PROMPT}, *history(), {"role": "user", "content": event_text}])
    except Exception as e:  # a bad model reply shouldn't crash the agent
        log("LLM call failed:", e)
        return
    remember("user", event_text)
    remember("assistant", json.dumps(decision, ensure_ascii=False))
    if decision.get("message"):
        msg = {"type": "send_message", "text": decision["message"], "why": (decision.get("why") or "coaching")[:140]}
        if decision.get("more"):
            msg["more"] = decision["more"]
        if decision.get("buttons"):
            msg["buttons"] = decision["buttons"]
        write(msg)
        reply = read()
        if reply["type"] == "rejected":
            log("message rejected:", reply["reason"], reply.get("detail"))
            if reply["reason"] in ("too_long", "too_many_pages"):
                write(msg)  # the harness splits it on the second try
                read()
    if decision.get("wakeup"):
        write({"type": "schedule_wakeup", "at": decision["wakeup"]["at"], "note": decision["wakeup"]["note"]})
        reply = read()
        if reply["type"] == "rejected":
            log("wakeup rejected:", reply["reason"])
    if decision.get("ask_if_achieved"):
        write({"type": "request_verification", "contract_id": decision["ask_if_achieved"],
               "why": (decision.get("why") or "might be done")[:140]})
        reply = read()
        if reply["type"] == "rejected":
            log("verification rejected:", reply["reason"])


def main():
    while True:
        ev = read()
        try:
            handle(ev)
        finally:
            write({"type": "done", "event_id": ev["id"]})


if __name__ == "__main__":
    main()
