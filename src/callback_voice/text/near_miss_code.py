from callback_voice.text.near_miss import NearMiss, near_miss
from callback_voice.text.spoken_code import spoken_code_stream
from callback_voice.text.spoken_code_match import normalize_entity


def near_miss_code(entity: str, transcript: str) -> NearMiss | None:
    """A code in ``transcript`` that is almost ``entity``: "B, X, 7, Q, 2" (swap) or
    "the X7 Q2" (partial) against DX7Q2. None when nothing close was said."""
    return near_miss(normalize_entity(entity), spoken_code_stream(transcript, loose=True))
