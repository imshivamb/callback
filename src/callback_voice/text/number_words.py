from typing import Final

UNITS: Final = {
    "zero": 0,
    "oh": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}
TENS: Final = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}


def number_at(words: list[str], i: int) -> tuple[int, int] | None:
    """Parse a number (digits or words up to 99) starting at ``words[i]``.

    Returns ``(value, tokens_consumed)`` or None. "twenty five" -> (25, 2).
    """
    if i >= len(words):
        return None
    word = words[i]
    if word.isdigit():
        return int(word), 1
    if word in UNITS:
        return UNITS[word], 1
    if word in TENS:
        nxt = words[i + 1] if i + 1 < len(words) else ""
        if nxt in UNITS and 0 < UNITS[nxt] < 10:
            return TENS[word] + UNITS[nxt], 2
        return TENS[word], 1
    return None
