from callback_voice.core.models.turn import Turn
from callback_voice.scoring.facts.carrying_words import carrying_words


def fact_word_confidence(turn: Turn, heard: str) -> float | None:
    """Lowest recogniser confidence among the words that spell ``heard``.

    Only those words count: an unsure "a" elsewhere in the sentence says nothing about
    the code. Falls back to the turn's mean confidence when they cannot be found.
    """
    words = carrying_words(turn, heard)
    return min(w.p for w in words) if words else turn.confidence
