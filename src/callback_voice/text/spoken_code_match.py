import re

from callback_voice.text.spoken_code import spoken_code_stream
from callback_voice.text.tokens import tokens


def normalize_entity(entity: str) -> str:
    """Canonical form of an expected entity: upper-case alphanumerics only."""
    return re.sub(r"[^A-Za-z0-9]", "", entity).upper()


def entity_spoken(entity: str, transcript: str) -> bool:
    """Whether ``entity`` was said in ``transcript``, however it was spelled out.

    Codes ("DX7Q2") match letter-by-letter speech, NATO spelling and digit words.
    Plain words and phrases ("Saturday", "Priya Sharma") match as whole tokens.
    """
    target = normalize_entity(entity)
    if not target:
        return False
    is_code = any(c.isdigit() for c in target) or (len(target) <= 6 and entity.isupper())
    if is_code:
        return any(target in run for run in spoken_code_stream(transcript, loose=True))
    wanted = tokens(entity)
    said = tokens(transcript)
    return any(said[i : i + len(wanted)] == wanted for i in range(len(said) - len(wanted) + 1))
