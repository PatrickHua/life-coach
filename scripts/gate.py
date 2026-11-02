"""PreToolUse hook: the nudge gate.

Claude Code passes the pending tool call as JSON on stdin.
Exit 0 lets it run. Exit 2 blocks it, and the message on stderr goes back to the model.
"""
import json
import sys
from datetime import datetime, timedelta

from common import SETUP_STEPS, config, now, read_jsonl, setup_state, write_jsonl

SETUP_TOOLS = ("create_trigger", "send_later")


def block(reason):
    print(f"Blocked by the nudge gate: {reason}", file=sys.stderr)
    sys.exit(2)


def in_quiet_hours(t, start, end):
    """Quiet hours like 22:00-08:00 wrap past midnight."""
    hm = t.strftime("%H:%M")
    return (start <= hm or hm < end) if start > end else (start <= hm < end)


def check_setup(tool):
    done = setup_state()
    if not done["cloud"]:
        block("setup step 1 (cloud) isn't done. Help the user open this repo in Claude Code on the web first.")
    # Scheduling is itself the last setup step, so it only needs the earlier steps.
    needed = SETUP_STEPS[:-1] if tool.endswith(SETUP_TOOLS) else SETUP_STEPS
    missing = [s for s in needed if not done[s]]
    if missing:
        block(f"finish setup first (next step: {missing[0]}).")


def check_push(cfg, session_id, message):
    t = now()
    gate = cfg.get("gate", {})
    if in_quiet_hours(t, gate.get("quiet_start", "22:00"), gate.get("quiet_end", "08:00")):
        block(f"quiet hours ({gate.get('quiet_start')}-{gate.get('quiet_end')}). Save it for the morning digest.")

    nudges = read_jsonl("nudges.jsonl")
    today = [n for n in nudges if n["at"][:10] == t.date().isoformat()]
    cap = gate.get("daily_cap", 3)
    if len(today) >= cap:
        block(f"daily cap of {cap} nudges reached. Add it to the next digest instead.")

    # Silence usually means the user forgot, not that they want quiet. So an unanswered
    # nudge only spaces out the next one; it never mutes the coach. Only the user can do that.
    if gate.get("paused"):
        block("the user paused the coach. Wait until they say to resume.")
    if nudges and not nudges[-1].get("replied"):
        last = datetime.fromisoformat(nudges[-1]["at"])
        gap = timedelta(hours=gate.get("retry_gap_hours", 3))
        if t - last < gap:
            block(f"the last nudge is still unanswered. Try again after {(last + gap):%a %H:%M}, worded differently.")

    nudges.append({"at": t.isoformat(timespec="seconds"), "session": session_id, "message": message, "replied": False})
    write_jsonl("nudges.jsonl", nudges)


def main():
    event = json.load(sys.stdin)
    tool = event.get("tool_name", "")
    check_setup(tool)
    if tool == "PushNotification":
        check_push(config(), event.get("session_id", ""), event.get("tool_input", {}).get("message", ""))
    sys.exit(0)


if __name__ == "__main__":
    main()
