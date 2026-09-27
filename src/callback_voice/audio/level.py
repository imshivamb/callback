"""Loudness helpers used for noise mixing and speech-level checks."""

import numpy as np

from callback_voice.audio.format import Audio

_FLOOR = 1e-10


def rms(audio: Audio) -> float:
    """Root-mean-square amplitude; 0.0 for empty input."""
    if audio.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(audio, dtype=np.float64))))


def rms_dbfs(audio: Audio) -> float:
    """RMS level in dBFS (full-scale sine is about -3 dBFS)."""
    return 20.0 * float(np.log10(max(rms(audio), _FLOOR)))


def gain_for_snr(signal_rms: float, noise_rms: float, snr_db: float) -> float:
    """Linear gain to apply to noise so that signal/noise equals ``snr_db``."""
    if noise_rms <= _FLOOR:
        return 0.0
    target_noise_rms = signal_rms / (10.0 ** (snr_db / 20.0))
    return float(target_noise_rms / noise_rms)
