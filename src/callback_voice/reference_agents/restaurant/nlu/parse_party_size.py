from callback_voice.text.number_words import number_at
from callback_voice.text.tokens import tokens

_AFTER = {"people", "person", "persons", "guests", "of", "pax", "adults", "diners"}
_BEFORE = {"for", "it"}


def parse_party_size(text: str) -> int | None:
    """ "table for 4", "5 people", "party of five", "make it 6", "there'll be 3 of us".

    "for 8pm" is a time, not a party of eight.
    """
    words = tokens(text.replace("-", " "))
    found = None
    for i in range(len(words)):
        parsed = number_at(words, i)
        if parsed is None:
            continue
        value, used = parsed
        after = words[i + used] if i + used < len(words) else ""
        before = words[i - 1] if i > 0 else ""
        two_before = " ".join(words[max(0, i - 2) : i])
        if after in {"pm", "am", "o'clock", "oclock", "thirty", "fifteen", "tonight"}:
            continue
        sized = after in _AFTER or before in _BEFORE or two_before == "party of"
        if sized and 1 <= value <= 20:
            found = value
    return found
