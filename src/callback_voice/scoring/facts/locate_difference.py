from callback_voice.core.models.turn import Turn
from callback_voice.scoring.facts.carrying_words import carrying_words
from callback_voice.text.spoken_code_match import normalize_entity

_WINDOW_S = 0.3


def locate_difference(turn: Turn, heard: str, expected: str) -> tuple[float, float] | None:
    """Estimate when the first differing character was spoken: a 0.3 s window placed
    proportionally along the words that spell ``heard`` (codes are read at an even pace).
    None when those words cannot be found.
    """
    words = carrying_words(turn, heard)
    if not words:
        return None
    target, want = normalize_entity(heard), normalize_entity(expected)
    covered = "".join(normalize_entity(w.text) for w in words)
    index = next((i for i, (a, b) in enumerate(zip(target, want, strict=False)) if a != b), 0)
    start, end = words[0].start_s, words[-1].end_s
    at = start + (end - start) * max(0, index - target.find(covered)) / max(1, len(covered))
    return at, at + _WINDOW_S
