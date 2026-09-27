import re
from typing import Final

from callback_voice.text.number_words import UNITS
from callback_voice.text.tokens import tokens

NATO: Final = {
    "alpha": "A",
    "alfa": "A",
    "bravo": "B",
    "charlie": "C",
    "delta": "D",
    "echo": "E",
    "foxtrot": "F",
    "golf": "G",
    "hotel": "H",
    "india": "I",
    "juliet": "J",
    "juliett": "J",
    "kilo": "K",
    "lima": "L",
    "mike": "M",
    "november": "N",
    "oscar": "O",
    "papa": "P",
    "quebec": "Q",
    "romeo": "R",
    "sierra": "S",
    "tango": "T",
    "uniform": "U",
    "victor": "V",
    "whiskey": "W",
    "whisky": "W",
    "xray": "X",
    "yankee": "Y",
    "zulu": "Z",
}
_LETTER_NAMES: Final = {
    "bee": "B",
    "be": "B",
    "see": "C",
    "sea": "C",
    "dee": "D",
    "ee": "E",
    "eff": "F",
    "gee": "G",
    "jay": "J",
    "kay": "K",
    "el": "L",
    "em": "M",
    "en": "N",
    "pee": "P",
    "queue": "Q",
    "cue": "Q",
    "are": "R",
    "ess": "S",
    "tee": "T",
    "you": "U",
    "vee": "V",
    "ex": "X",
    "why": "Y",
    "zed": "Z",
    "zee": "Z",
}
_DIGIT_WORDS: Final = {w: str(v) for w, v in UNITS.items() if v < 10}
_MAX_TOKEN_LEN = 6
# "a" and "I" are almost always words, not code letters; say "alpha"/"india" instead.
_ARTICLES: Final = frozenset({"a", "i"})


def code_symbols(token: str, *, loose: bool) -> str | None:
    """The code characters one spoken token stands for, or None if it is ordinary speech.

    ``loose`` also accepts letter names ("dee", "why") that collide with ordinary words;
    it is used when checking for an entity that is known to be present.
    """
    if token in NATO:
        return NATO[token]
    if token in _DIGIT_WORDS:
        return _DIGIT_WORDS[token]
    if loose and token in _LETTER_NAMES:
        return _LETTER_NAMES[token]
    if not loose and token in _ARTICLES:
        return None
    if re.fullmatch(r"\d{1,2}(?:am|pm)", token):  # "8pm" is a time, not code characters
        return None
    if len(token) <= _MAX_TOKEN_LEN and re.fullmatch(r"[a-z0-9]+", token):
        is_single_letter = len(token) == 1 and token.isalpha()
        has_digit = any(c.isdigit() for c in token)
        if is_single_letter or has_digit:
            return token.upper()
    return None


def spoken_code_stream(text: str, *, loose: bool = False) -> list[str]:
    """Collapse runs of code-like tokens into contiguous strings.

    "my ref is D X seven Q two, thanks" -> ["DX7Q2"]. Handles "double seven".
    """
    runs: list[str] = []
    current = ""
    words = tokens(text.replace("x-ray", "xray"))
    i = 0
    while i < len(words):
        word = words[i]
        if word in {"double", "triple"} and i + 1 < len(words):
            symbol = code_symbols(words[i + 1], loose=loose)
            if symbol is not None and len(symbol) == 1:
                current += symbol * (2 if word == "double" else 3)
                i += 2
                continue
        symbol = code_symbols(word, loose=loose)
        if symbol is None:
            if current:
                runs.append(current)
            current = ""
        else:
            current += symbol
        i += 1
    if current:
        runs.append(current)
    return runs


def find_code(text: str, length: int = 5) -> str | None:
    """The first spoken alphanumeric code of ``length`` with at least one letter and digit."""
    for run in spoken_code_stream(text):
        for start in range(0, len(run) - length + 1):
            candidate = run[start : start + length]
            if any(c.isdigit() for c in candidate) and any(c.isalpha() for c in candidate):
                return candidate
    return None
