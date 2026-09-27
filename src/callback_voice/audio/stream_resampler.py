from math import gcd

import numpy as np

from callback_voice.audio.format import Audio
from callback_voice.audio.resample import resample

_SUPPORT = 32  # input samples of filter support needed on each side


class StreamResampler:
    """Click-free resampling of a live stream delivered in arbitrary chunks.

    Overlap-save: the buffer always starts with ``margin`` samples of already-emitted
    context and ends with ``margin`` samples of lookahead, so every emitted sample
    sees the full filter. Adds ``margin`` input samples of latency (about 2 ms).
    """

    def __init__(self, from_rate: int, to_rate: int) -> None:
        self._from, self._to = from_rate, to_rate
        divisor = gcd(from_rate, to_rate)
        self._up, self._down = to_rate // divisor, from_rate // divisor
        self._margin = self._down * -(-_SUPPORT // self._down)
        self._buffer = np.zeros(self._margin, dtype=np.float32)

    def process(self, chunk: Audio) -> Audio:
        if self._from == self._to:
            return chunk
        self._buffer = np.concatenate([self._buffer, chunk.astype(np.float32)])
        margin = self._margin
        emit = ((self._buffer.size - 2 * margin) // self._down) * self._down
        if emit <= 0:
            return np.zeros(0, dtype=np.float32)
        out = resample(self._buffer[: 2 * margin + emit], self._from, self._to)
        start = margin * self._up // self._down
        result = out[start : start + emit * self._up // self._down]
        self._buffer = self._buffer[emit:]
        return result.astype(np.float32)
