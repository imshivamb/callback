import re
from typing import Final

_INTERRUPTING_WORDS: Final = frozenset(
    {
        "sorry",
        "wait",
        "stop",
        "no",
        "nope",
        "hold",
        "actually",
        "excuse",
        "pardon",
        "hello",
        "hey",
        "but",
        "nahi",
        "ruko",
        "listen",
        "hang",
    }
)


def sounds_like_interruption(partial_transcript: str) -> bool:
    """Does a partial transcript of the caller, heard mid-sentence, mean "let me talk"?

    Yes for two or more words, any number, or one word people interrupt with
    ("sorry", "wait", "no"). A lone short token is not enough: fast STT turns a
    hummed "mm-hmm" into "Amen." or "Hi." often enough that yielding on it would make
    the agent stop for acknowledgements.
    """
    words = re.findall(r"[a-z0-9']+", partial_transcript.lower())
    if len(words) >= 2 or any(any(c.isdigit() for c in w) for w in words):
        return True
    return bool(words) and words[0] in _INTERRUPTING_WORDS
