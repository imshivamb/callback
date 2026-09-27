import re

_TOKEN = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")


def tokens(text: str) -> list[str]:
    """Lower-case word tokens; punctuation and hyphens split words ("D-X-7" -> d, x, 7)."""
    return _TOKEN.findall(text.lower())
