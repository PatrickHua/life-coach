"""UserPromptSubmit hook: when the user writes, mark this session's nudges as answered.

Scheduled wake-ups also arrive as prompts: either the [coach:...] text itself, or a
system notice telling the session that a scheduled task fired. Neither counts as a reply.
"""
import json
import sys

from common import read_jsonl, write_jsonl


AUTOMATED_MARKERS = ("[coach:", "<task-notification>", "SYSTEM NOTIFICATION - NOT USER INPUT")


def is_from_user(prompt):
    return not any(marker in prompt for marker in AUTOMATED_MARKERS)


def main():
    event = json.load(sys.stdin)
    session_id = event.get("session_id")
    prompt = event.get("prompt", "")
    if not session_id or not is_from_user(prompt):
        return
    nudges = read_jsonl("nudges.jsonl")
    changed = False
    for n in nudges:
        if n.get("session") == session_id and not n.get("replied"):
            n["replied"] = True
            changed = True
    if changed:
        write_jsonl("nudges.jsonl", nudges)


if __name__ == "__main__":
    main()
