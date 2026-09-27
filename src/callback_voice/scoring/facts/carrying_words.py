from callback_voice.core.models.turn import Turn, TurnWord
from callback_voice.text.spoken_code_match import normalize_entity


def carrying_words(turn: Turn, heard: str) -> list[TurnWord]:
    """The transcribed words that spell ``heard`` ("BX7Q2," or "B,", "X,", "7", ...).

    Anchors on the longest word that is part of the value and extends over neighbours
    that continue it, so a stray "7" elsewhere in the sentence is not mistaken for it.
    """
    target = normalize_entity(heard)
    parts = [normalize_entity(w.text) for w in turn.words]
    candidates = [i for i, p in enumerate(parts) if p and p in target]
    if not candidates:
        return []
    anchor = max(candidates, key=lambda i: len(parts[i]))
    first = last = anchor
    covered = parts[anchor]
    while first > 0 and parts[first - 1] and parts[first - 1] + covered in target:
        first -= 1
        covered = parts[first] + covered
    while last + 1 < len(parts) and parts[last + 1] and covered + parts[last + 1] in target:
        last += 1
        covered += parts[last]
    return turn.words[first : last + 1]
