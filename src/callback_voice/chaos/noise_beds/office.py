import numpy as np

from callback_voice.audio.format import SAMPLE_RATE, Audio
from callback_voice.chaos.noise_beds.shaped_noise import shaped_noise


def office(rng: np.random.Generator, seconds: float) -> Audio:
    """HVAC hum and air, with keyboard clicks."""
    n = round(seconds * SAMPLE_RATE)
    t = np.arange(n) / SAMPLE_RATE
    hum = 0.3 * np.sin(2 * np.pi * 120 * t) + 0.15 * np.sin(2 * np.pi * 240 * t)
    bed = shaped_noise(rng, seconds, slope=1.2) + hum.astype(np.float32)
    click = np.arange(round(0.01 * SAMPLE_RATE))
    for start in rng.integers(0, max(1, n - click.size), size=round(seconds * 4)):
        bed[start : start + click.size] += rng.normal(0, 1.5, click.size).astype(
            np.float32
        ) * np.exp(-click / 30)
    return bed
