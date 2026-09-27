import re
from dataclasses import dataclass
from typing import Literal

from callback_voice.core.models.expected_fact import ExpectedFact
from callback_voice.text.digit_runs import digit_runs
from callback_voice.text.find_counts import find_counts
from callback_voice.text.find_times import find_times
from callback_voice.text.near_miss import near_miss
from callback_voice.text.near_miss_code import near_miss_code
from callback_voice.text.spoken_code_match import entity_spoken

type MatchStatus = Literal["said", "near_miss", "absent"]


@dataclass(frozen=True, slots=True)
class FactMatch:
    status: MatchStatus
    heard: str | None = None
    partial: bool = False
    """A near miss with characters missing or extra rather than swapped."""


def match_fact(fact: ExpectedFact, text: str) -> FactMatch:
    """Whether ``text`` (one agent turn) contains the fact, a near miss, or neither."""
    match fact.kind:
        case "code":
            if entity_spoken(fact.value, text):
                return FactMatch("said")
            miss = near_miss_code(fact.value, text)
            if miss is None:
                return FactMatch("absent")
            return FactMatch("near_miss", " ".join(miss.value), partial=miss.partial)
        case "count":
            counts = find_counts(text, fact.of)
            if int(fact.value) in counts:
                return FactMatch("said")
            return (
                FactMatch("near_miss", f"{counts[0]} {fact.of}") if counts else FactMatch("absent")
            )
        case "time":
            want = find_times(fact.value)
            said = find_times(text)
            if want and want[0] in said:
                return FactMatch("said")
            return FactMatch("near_miss", _fmt_time(said[0])) if said else FactMatch("absent")
        case "phone":
            want_digits = re.sub(r"\D", "", fact.value)
            runs = digit_runs(text)
            if any(want_digits in run for run in runs):
                return FactMatch("said")
            close = near_miss(want_digits, runs)
            return (
                FactMatch("near_miss", close.value, partial=close.partial)
                if close
                else FactMatch("absent")
            )
        case "text":
            return FactMatch("said") if entity_spoken(fact.value, text) else FactMatch("absent")


def _fmt_time(value: tuple[int, int]) -> str:
    hour, minute = value
    return f"{hour % 12 or 12}:{minute:02d} {'PM' if hour >= 12 else 'AM'}"
