"""PCM16 little-endian conversion at the transport boundary."""

import numpy as np

from callback_voice.audio.format import Audio


def to_pcm16(audio: Audio) -> bytes:
    """Encode float audio as PCM16 LE, clipping anything outside [-1, 1]."""
    clipped = np.clip(audio, -1.0, 1.0)
    return (clipped * 32767.0).astype("<i2").tobytes()


def from_pcm16(data: bytes) -> Audio:
    """Decode PCM16 LE bytes; a trailing odd byte is dropped."""
    usable = len(data) - (len(data) % 2)
    ints = np.frombuffer(data[:usable], dtype="<i2")
    return (ints.astype(np.float32) / 32768.0).astype(np.float32)
