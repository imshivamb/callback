from callback_voice.text.spoken_code import spoken_code_stream
from callback_voice.text.spoken_code_match import normalize_entity

_MAX_DIFFERENCES = 2


def near_miss_code(entity: str, transcript: str) -> str | None:
    """A code in ``transcript`` that is almost ``entity`` (1–2 characters different).

    "Your reference is B, X, 7, Q, 2" against DX7Q2 returns "BX7Q2": the agent said a
    code, but the wrong one. Returns None when nothing close was said.
    """
    target = normalize_entity(entity)
    for run in spoken_code_stream(transcript, loose=True):
        for start in range(0, len(run) - len(target) + 1):
            candidate = run[start : start + len(target)]
            differences = sum(a != b for a, b in zip(candidate, target, strict=True))
            if 0 < differences <= _MAX_DIFFERENCES:
                return candidate
    return None
