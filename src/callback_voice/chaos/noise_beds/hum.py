import numpy as np

from callback_voice.audio.format import SAMPLE_RATE, Audio
from callback_voice.chaos.noise_beds.shaped_noise import shaped_noise


def hum(rng: np.random.Generator, seconds: float) -> Audio:
    """Mains hum with harmonics over line hiss: a bad landline."""
    t = np.arange(round(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    tone = sum(np.sin(2 * np.pi * 50 * k * t) / k for k in (1, 2, 3, 5))
    return (
        np.asarray(tone, dtype=np.float32) + 0.4 * shaped_noise(rng, seconds, slope=0.0)
    ).astype(np.float32)
