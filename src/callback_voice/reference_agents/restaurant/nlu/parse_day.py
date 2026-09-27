from typing import Final

from callback_voice.text.tokens import tokens

DAYS: Final = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
# The agent's world is fixed so conversations are reproducible: today is Thursday.
TODAY: Final = "thursday"
_ALIASES: Final = {
    "mon": "monday",
    "tue": "tuesday",
    "tues": "tuesday",
    "wed": "wednesday",
    "thu": "thursday",
    "thurs": "thursday",
    "fri": "friday",
    "sat": "saturday",
    "sun": "sunday",
    "shanivaar": "saturday",
    "shaniwar": "saturday",
    "ravivaar": "sunday",
    "today": TODAY,
    "tonight": TODAY,
    "tomorrow": "friday",
}


def parse_day(text: str) -> str | None:
    """The last weekday mentioned ("not Friday, Saturday" -> saturday), or None."""
    found = None
    for word in tokens(text):
        day = word if word in DAYS else _ALIASES.get(word)
        if day is not None:
            found = day
    return found
