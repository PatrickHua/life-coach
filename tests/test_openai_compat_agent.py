"""The example LLM agent against a fake OpenAI-compatible server (no real model)."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from conftest import onboard_with_goal

REPLIES = []
REQUESTS = []


class FakeLLM(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        REQUESTS.append(body)
        content = json.dumps(REPLIES.pop(0)) if REPLIES else '{"message": null}'
        out = json.dumps({"choices": [{"message": {"role": "assistant", "content": content}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


@pytest.fixture
def fake_llm(monkeypatch):
    server = HTTPServer(("127.0.0.1", 0), FakeLLM)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("LLM_BASE_URL", f"http://127.0.0.1:{server.server_port}/v1")
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    REPLIES.clear()
    REQUESTS.clear()
    yield
    server.shutdown()


async def test_llm_agent_end_to_end(make_harness, fake_llm):
    REPLIES.append({"message": "Love it! When's your first run?", "buttons": ["Tomorrow", "Today"],
                    "why": "get a first step"})
    h, t = await make_harness(agent="openai_compat")
    cid = await onboard_with_goal(h, t)
    assert t.last == "Love it! When's your first run?"
    assert REQUESTS[0]["model"] == "fake-model"
    assert REQUESTS[0]["messages"][0]["role"] == "system"
    REPLIES.append({"message": "Nice, I'll check in tonight.", "why": "plan check-in",
                    "wakeup": {"at": "2026-11-04T19:00:00+00:00", "note": "ask about the run"},
                    "ask_if_achieved": None})
    await h.on_button(t.button("Today"))
    assert t.last == "Nice, I'll check in tonight."
    assert [w["note"] for w in h.state["wakeups"].values()] == ["ask about the run"]
    assert len(REQUESTS[1]["messages"]) == 4  # system + remembered turn + new event
    REPLIES.append({"message": "All 12 runs? Amazing.", "why": "user says finished", "ask_if_achieved": cid})
    await h.on_text("finished my 12th run!")
    assert t.last.startswith("Goal check:")
