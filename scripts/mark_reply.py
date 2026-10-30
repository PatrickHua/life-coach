"""UserPromptSubmit hook: when the user writes, mark this session's nudges as answered.

Scheduled wake-ups also arrive as prompts. They start with a [coach:...] tag,
so they're skipped here and don't count as replies.
"""
import json
import sys

from common import read_jsonl, write_jsonl


def main():
    event = json.load(sys.stdin)
    session_id = event.get("session_id")
    if not session_id or event.get("prompt", "").lstrip().startswith("[coach:"):
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
