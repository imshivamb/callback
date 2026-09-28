import re
from typing import Final

from callback_voice.reference_agents.restaurant.voice.split_sentences import split_sentences

# Openings the agent's replies often start with. Spoken on their own they are short
# and, pre-synthesised at start-up, play at once even on a machine that has never
# heard the rest of the reply.
LEAD_PHRASES: Final = (
    "Sure,",
    "Great,",
    "No problem.",
    "Of course.",
    "Done.",
    "Got it,",
    "Thanks,",
)
_MIN_REST_WORDS = 4  # a short sentence is quick to synthesise whole, and sounds better
_LEAD = re.compile(r"^((?:\S+\s){0,2}\S+,)\s+(\S.*)$")


def speech_chunks(text: str) -> list[str]:
    """Sentences to synthesise and play in order, with a short opening chunk first.

    A first sentence that opens with a brief phrase and a comma ("Sure, I can help
    move your booking.") is split after the comma, so the agent starts speaking after
    synthesising three words or fewer instead of the whole sentence.
    """
    sentences = split_sentences(text)
    lead = _LEAD.match(sentences[0]) if sentences else None
    if lead is not None and len(lead.group(2).split()) >= _MIN_REST_WORDS:
        return [lead.group(1), lead.group(2), *sentences[1:]]
    return sentences
