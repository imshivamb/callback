"""In-band DTMF tone generation for transports without an out-of-band DTMF channel."""

import numpy as np

from callback_voice.audio.format import SAMPLE_RATE, Audio

_ROWS = {
    "1": 697,
    "2": 697,
    "3": 697,
    "A": 697,
    "4": 770,
    "5": 770,
    "6": 770,
    "B": 770,
    "7": 852,
    "8": 852,
    "9": 852,
    "C": 852,
    "*": 941,
    "0": 941,
    "#": 941,
    "D": 941,
}
_COLS = {
    "1": 1209,
    "4": 1209,
    "7": 1209,
    "*": 1209,
    "2": 1336,
    "5": 1336,
    "8": 1336,
    "0": 1336,
    "3": 1477,
    "6": 1477,
    "9": 1477,
    "#": 1477,
    "A": 1633,
    "B": 1633,
    "C": 1633,
    "D": 1633,
}


def dtmf_tones(digits: str, tone_s: float = 0.12, gap_s: float = 0.08) -> Audio:
    """Render ``digits`` as ITU-T Q.23 dual tones separated by short gaps."""
    t = np.arange(round(tone_s * SAMPLE_RATE), dtype=np.float32) / SAMPLE_RATE
    gap = np.zeros(round(gap_s * SAMPLE_RATE), dtype=np.float32)
    parts: list[Audio] = []
    for digit in digits.upper():
        if digit not in _ROWS:
            raise ValueError(f"not a DTMF digit: {digit!r}")
        tone = 0.35 * (np.sin(2 * np.pi * _ROWS[digit] * t) + np.sin(2 * np.pi * _COLS[digit] * t))
        parts.extend([tone.astype(np.float32), gap])
    return np.concatenate(parts) if parts else np.zeros(0, dtype=np.float32)
