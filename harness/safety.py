"""A fixed crisis response that doesn't depend on any agent getting it right."""
import re

_PATTERNS = [
    r"\bkill(ing)? my ?self\b", r"\bsuicid", r"\bend (it all|my life)\b", r"\bwant to die\b",
    r"\bself[- ]?harm", r"\bhurt(ing)? my ?self\b", r"\bno reason to live\b",
]
_CRISIS = re.compile("|".join(_PATTERNS), re.I)

CRISIS_MESSAGE = (
    "I'm really glad you told me. You deserve support from a real person right now. "
    "Please reach out to someone you trust, or a crisis line: findahelpline.com lists free, "
    "confidential lines in your country. If you're in danger, call your local emergency number. "
    "I've paused coaching. Send /resume whenever you want."
)


def is_crisis(text: str) -> bool:
    return bool(_CRISIS.search(text))
