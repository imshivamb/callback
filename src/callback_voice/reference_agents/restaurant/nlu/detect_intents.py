import re
from typing import Final, Literal

type Intent = Literal[
    "move", "new", "cancel", "human", "repeat", "goodbye", "yes", "no", "window", "check"
]

_PATTERNS: Final[dict[Intent, str]] = {
    "move": r"\b(move|change|reschedul\w*|push|shift|switch|different (day|time))\b",
    "new": r"\b(new (booking|reservation)|book (a|me)|make a (booking|reservation)|reserve|"
    r"a table for)\b",
    "cancel": r"\bcancel\w*\b",
    "human": r"\b(human|real person|a person|someone|representative|manager|staff|operator|"
    r"talk to (a|an|some)\w*)\b",
    "repeat": r"\b(repeat|say (that|it) again|didn'?t (catch|get|hear)|pardon|come again|"
    r"one more time)\b",
    "goodbye": r"\b(bye|goodbye|that'?s (all|it)|nothing else|all set|no,? thanks?|no thank you)\b",
    "yes": r"\b(yes|yeah|yep|yup|sure|correct|right|perfect|great|go ahead|please do|"
    r"that works|sounds good|works for me|okay|ok|fine|haan|ha|ji|confirm\w*)\b",
    "no": r"\b(no|nope|not really|nahi|nah|don'?t)\b",
    "window": r"\bwindow\b",
    "check": r"\b(check|confirm my|what time is my|look up)\b",
}


def detect_intents(text: str) -> set[Intent]:
    """All intents present in one utterance; the dialog decides which one wins."""
    lowered = text.lower()
    found: set[Intent] = {intent for intent, rx in _PATTERNS.items() if re.search(rx, lowered)}
    if "goodbye" in found:
        found.discard("no")
    return found
