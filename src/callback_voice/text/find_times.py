import re

from callback_voice.text.number_words import number_at
from callback_voice.text.tokens import tokens

_CLOCK = re.compile(
    r"\b(\d{1,2})(?:\s*[:.,]\s*(\d{2})|(\d{2}))?\s*(a\.?\s?m\.?|p\.?\s?m\.?)?(?![\d])",
    re.IGNORECASE,
)


def find_times(text: str, *, assume_pm: bool = True) -> list[tuple[int, int]]:
    """Clock times said in ``text`` as (hour 0–23, minute).

    Handles how speech recognition writes times: "7:30 PM", "7.30pm", "7, 30 p.m.",
    "730 p.m.", "19:00", and words ("seven thirty p.m."). Bare hours count only with
    am/pm or a minute. With ``assume_pm``, hours 1–11 without am/pm are read as evening.
    """
    found: list[tuple[int, int]] = []
    for match in _CLOCK.finditer(text):
        hour, minute_a, minute_b, meridiem = match.groups()
        minute = minute_a or minute_b
        if minute is None and meridiem is None:
            continue
        found.append(_to_24h(int(hour), int(minute or 0), meridiem, assume_pm))
    words = tokens(text)
    for i in range(len(words)):
        parsed = number_at(words, i)
        if parsed is None or words[i].isdigit():
            continue
        hour, used = parsed
        after = words[i + used : i + used + 3]
        minute = number_at(words, i + used)
        meridiem = next((w for w in after if w in {"am", "pm", "a", "p"}), None)
        if minute and minute[0] in {15, 30, 45}:
            found.append(_to_24h(hour, minute[0], meridiem, assume_pm))
        elif meridiem in {"am", "pm"}:
            found.append(_to_24h(hour, 0, meridiem, assume_pm))
    return found


def _to_24h(hour: int, minute: int, meridiem: str | None, assume_pm: bool) -> tuple[int, int]:
    mark = (meridiem or "").lower().replace(".", "").replace(" ", "")
    if mark.startswith("p") or (not mark and assume_pm and 1 <= hour <= 11):
        hour = hour % 12 + 12
    elif mark.startswith("a") and hour == 12:
        hour = 0
    return hour, minute
