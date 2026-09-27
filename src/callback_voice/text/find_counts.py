from callback_voice.text.number_words import number_at
from callback_voice.text.tokens import tokens

_UNIT_WORDS = {"people": {"people", "persons", "guests", "of", "adults", "diners"}}
_LEADS = {"people": {("table", "for"), ("party", "of"), ("for",)}}


def find_counts(text: str, of: str = "people") -> list[int]:
    """Numbers said as a count of ``of``: "table for 5", "five people", "party of 4".

    A bare number is not counted, so the digits of a phone number or a time never
    pass for a party size.
    """
    units = _UNIT_WORDS.get(of, {of, of.rstrip("s")})
    leads = _LEADS.get(of, set())
    words = tokens(text.replace("-", " "))
    counts: list[int] = []
    for i in range(len(words)):
        parsed = number_at(words, i)
        if parsed is None:
            continue
        value, used = parsed
        after = words[i + used] if i + used < len(words) else ""
        before = tuple(words[max(0, i - 2) : i])
        counted = after in units or any(before[-len(lead) :] == lead for lead in leads if lead)
        if counted and after not in {"pm", "am", "p", "a"}:  # "for 8 pm" is a time
            counts.append(value)
    return counts
