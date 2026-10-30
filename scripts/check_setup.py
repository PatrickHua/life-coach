"""SessionStart hook: check setup progress and tell the model where things stand.

Whatever this prints is added to the conversation as context.
The cloud step is detected live; the other steps are recorded by
`mark_setup.py` after the model has tested them.
"""
from common import SETUP_STEPS, now, setup_state

NEXT_STEP_HINTS = {
    "cloud": "Running on a local machine. The coach needs Claude Code on the web so it can run while the user's computer is off.",
    "calendar": "Google Calendar is not connected or not tested yet.",
    "gmail": "Gmail is not connected or not tested yet.",
    "home": "This session isn't recorded as the coach's home session yet.",
    "schedules": "Scheduled tasks (heartbeat, morning brief, weekly review) are not created yet.",
}


def main():
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
