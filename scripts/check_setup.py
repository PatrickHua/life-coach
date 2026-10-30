"""SessionStart hook: check setup progress and tell the model where things stand.

Whatever this prints is added to the conversation as context.
The cloud step is detected live; the other steps are recorded by
`mark_setup.py` after the model has tested them.
"""
import subprocess

from common import ROOT, SETUP_STEPS, now, setup_state

NEXT_STEP_HINTS = {
    "cloud": "Running on a local machine. The coach needs Claude Code on the web so it can run while the user's computer is off.",
    "calendar": "Google Calendar is not connected or not tested yet.",
    "gmail": "Gmail is not connected or not tested yet.",
    "home": "This session isn't recorded as the coach's home session yet.",
    "schedules": "Scheduled tasks (heartbeat, morning brief, weekly review) are not created yet.",
}


def check_for_update():
    """Print a line if the GitHub repo has newer code. Never fails the hook."""
    try:
        git = ["git", "-C", str(ROOT)]
        subprocess.run(git + ["fetch", "--quiet", "origin"], timeout=15, check=True, capture_output=True)
        behind = subprocess.run(git + ["rev-list", "--count", "HEAD..@{upstream}"],
                                timeout=5, check=True, capture_output=True, text=True).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return
    if behind and behind != "0":
        print(f"UPDATE: {behind} new change(s) to the coach are available. Mention it once; use the update skill if the user agrees.")


def main():
    check_for_update()
    done = setup_state()
    missing = [s for s in SETUP_STEPS if not done[s]]
    if not missing:
        print(f"SETUP: complete. Local time {now():%a %Y-%m-%d %H:%M}.")
        return
    step = missing[0]
    position = SETUP_STEPS.index(step) + 1
    print(f"SETUP: incomplete, step {position} of {len(SETUP_STEPS)} ({step}). {NEXT_STEP_HINTS[step]}")
    print("Use the setup skill to help the user with this step only.")


if __name__ == "__main__":
    main()
