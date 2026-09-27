"""Rational-ratio resampling with a windowed-sinc polyphase filter.

Small and dependency-free (no scipy). Quality is well beyond what VAD, STT and
telephone-band audio need.
"""

from functools import cache
from math import gcd

import numpy as np
from numpy.typing import NDArray

from callback_voice.audio.format import Audio

_TAPS_PER_PHASE = 24
_KAISER_BETA = 8.6


def resample(audio: Audio, from_rate: int, to_rate: int) -> Audio:
    """Resample mono float audio from ``from_rate`` to ``to_rate``."""
    if from_rate == to_rate or audio.size == 0:
        return audio.astype(np.float32, copy=False)
    divisor = gcd(from_rate, to_rate)
    up, down = to_rate // divisor, from_rate // divisor
    kernel = _lowpass_kernel(up, down)

    stuffed = np.zeros(audio.size * up, dtype=np.float32)
    stuffed[::up] = audio
    filtered = np.convolve(stuffed, kernel, mode="full")

    delay = (kernel.size - 1) // 2
    out_len = -(-audio.size * up // down)
    return filtered[delay : delay + out_len * down : down].astype(np.float32)


@cache
def _lowpass_kernel(up: int, down: int) -> NDArray[np.float32]:
    cutoff = 1.0 / max(up, down)
    half = _TAPS_PER_PHASE * max(up, down) // 2
    n = np.arange(-half, half + 1, dtype=np.float64)
    taps = cutoff * np.sinc(cutoff * n) * np.kaiser(n.size, _KAISER_BETA)
    return (taps * up).astype(np.float32)
