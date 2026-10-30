"""Record a setup step as done, after the model has tested it.

Usage: python3 scripts/mark_setup.py <step> "<evidence>"
The cloud step can't be marked by hand; check_setup.py detects it.
"""
import sys

from common import SETUP_STEPS, is_cloud, load_json, now, save_json


def main():
    if len(sys.argv) < 3:
        sys.exit("usage: mark_setup.py <step> <evidence>")
    step, evidence = sys.argv[1], " ".join(sys.argv[2:])
    if step not in SETUP_STEPS or step == "cloud":
        sys.exit(f"unknown or automatic step: {step}")
    if not is_cloud():
        sys.exit("Finish the cloud step first: open this repo in Claude Code on the web.")
    state = load_json("setup.json", {})
    state[step] = {"done": True, "at": now().isoformat(timespec="minutes"), "evidence": evidence}
    save_json("setup.json", state)
    print(f"marked {step} as done")


if __name__ == "__main__":
    main()
