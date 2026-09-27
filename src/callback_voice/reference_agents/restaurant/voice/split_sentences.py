import re

_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")


def split_sentences(text: str) -> list[str]:
    """Split a reply into sentences so speech can start after the first one is synthesised."""
    return [part.strip() for part in _BOUNDARY.split(text.strip()) if part.strip()]
