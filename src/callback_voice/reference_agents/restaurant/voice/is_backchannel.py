import re
from typing import Final

_BACKCHANNEL: Final = re.compile(
    r"^(m+|h?m+[- ]?h?m+|uh[- ]?huh|mhm|ok(ay)?|yeah|yep|yes|right|sure|got it|i see|"
    r"alright|haan|ha|achha|acha|ji|hmm+|mm+[- ]?hmm+|uh|um)$"
)


def is_backchannel(transcript: str) -> bool:
    """Whether a short utterance is only an acknowledgement ("mm-hmm", "okay", "haan").

    Empty transcripts count: Whisper often returns nothing for a bare "hmm".
    """
    words = re.sub(r"[^a-z\s-]", "", transcript.lower()).strip()
    if not words:
        return True
    chunks = [c for c in re.split(r"[\s,]+", words) if c]
    return (len(chunks) <= 3 and all(_BACKCHANNEL.match(c) for c in chunks)) or bool(
        _BACKCHANNEL.match(words)
    )
