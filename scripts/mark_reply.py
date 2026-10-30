"""UserPromptSubmit hook: when the user writes in a session, mark that session's nudges as answered.

Matching on session id keeps a scheduled task's own opening prompt from counting
as a reply to nudges sent in other sessions.
"""
import json
import sys

from common import read_jsonl, write_jsonl


def main():
    event = json.load(sys.stdin)
    session_id = event.get("session_id")
    if not session_id:
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
