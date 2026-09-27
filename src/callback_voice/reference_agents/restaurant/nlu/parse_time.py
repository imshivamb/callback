import re
from dataclasses import dataclass

from callback_voice.text.number_words import number_at
from callback_voice.text.tokens import tokens

_OPEN_HOUR = 17
_CLOSE_HOUR = 22


@dataclass(frozen=True, slots=True)
class TimeRequest:
    """An exact time (``hour``/``minute``) or an acceptable range (``earliest``..``latest``)."""

    hour: int | None = None
    minute: int = 0
    earliest: int | None = None
    latest: int | None = None

    @property
    def is_range(self) -> bool:
        return self.earliest is not None


def parse_time(text: str, *, expecting_time: bool = False) -> TimeRequest | None:
    """Dinner times as people say them: "8pm", "seven thirty", "half past 7",
    "19:00", "between seven and nine", "7 to 9pm", "anytime after 7", and Whisper's "730".

    Bare hours are read as evening, since the restaurant serves dinner only. With
    ``expecting_time`` (the agent just asked for a time) a lone number counts too.
    """
    lowered = text.lower().replace("p.m.", "pm").replace("a.m.", "am")
    # "7:30", "7.30", and Whisper's compact "730" / "1930" all mean a clock time.
    clock = re.search(r"\b(\d{1,2})[:.](\d{2})\b", lowered) or re.search(
        r"\b(\d{1,2})(00|15|30|45)\b", lowered
    )
    if clock:
        return TimeRequest(hour=_evening(int(clock.group(1))), minute=int(clock.group(2)))
    words = tokens(re.sub(r"(\d)(am|pm)\b", r"\1 \2", lowered).replace("-", " to "))
    hours = _hour_mentions(words, expecting_time)
    if not hours:
        return None
    if len(hours) >= 2 and _mentions_range(words):
        lo, hi = sorted((hours[0][0], hours[1][0]))
        return TimeRequest(earliest=lo, latest=hi)
    hour, minute = hours[-1]
    if "after" in words:
        return TimeRequest(earliest=hour, latest=_CLOSE_HOUR)
    if "before" in words:
        return TimeRequest(earliest=_OPEN_HOUR, latest=hour)
    return TimeRequest(hour=hour, minute=minute)


def _hour_mentions(words: list[str], expecting: bool) -> list[tuple[int, int]]:
    found: list[tuple[int, int]] = []
    i = 0
    while i < len(words):
        if words[i] == "half" and i + 2 < len(words) and words[i + 1] == "past":
            parsed = number_at(words, i + 2)
            if parsed and 1 <= parsed[0] <= 12:
                found.append((_evening(parsed[0]), 30))
                i += 2 + parsed[1]
                continue
        parsed = number_at(words, i)
        if parsed is None or not _is_time_context(words, i, parsed[1], expecting):
            i += 1
            continue
        value, used = parsed
        minute = 0
        after = number_at(words, i + used)
        if after and after[0] in (15, 30, 45):
            minute, used = after[0], used + after[1]
        if 1 <= value <= 23:
            found.append((_evening(value), minute))
        i += used
    return found


_SUFFIXES = frozenset({"pm", "am", "o'clock", "oclock"})
_PARTY_WORDS = frozenset({"people", "person", "persons", "guests", "of", "pax", "adults", "us"})
_LEADS = frozenset(
    {
        "at",
        "around",
        "about",
        "between",
        "after",
        "before",
        "from",
        "to",
        "and",
        "or",
        "by",
        "till",
        "until",
    }
)
_FOLLOWS = frozenset({"to", "and", "or", "thirty", "fifteen", "tonight"})


def _is_time_context(words: list[str], i: int, used: int, expecting: bool) -> bool:
    before = words[i - 1] if i > 0 else ""
    after = words[i + used] if i + used < len(words) else ""
    if after in _PARTY_WORDS:
        return False
    if after in _SUFFIXES:
        return True
    if before in {"for", "it"}:  # "table for 4", "make it 5"
        return False
    return before in _LEADS or after in _FOLLOWS or expecting


def _mentions_range(words: list[str]) -> bool:
    return any(
        w in words for w in ("between", "to", "and", "or", "till", "until", "anytime", "any")
    )


def _evening(hour: int) -> int:
    return hour + 12 if 1 <= hour <= 11 else hour
