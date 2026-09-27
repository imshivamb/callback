import numpy as np

from callback_voice.audio.format import SAMPLE_RATE, Audio
from callback_voice.chaos.noise_beds.shaped_noise import envelope, shaped_noise


def cafe(rng: np.random.Generator, seconds: float) -> Audio:
    """Crowd babble (speech-band noise with syllable-rate modulation) and cup clinks."""
    babble = sum(
        shaped_noise(rng, seconds, slope=1.0, low_hz=200, high_hz=3_500)
        * envelope(rng, seconds, 4.0, 0.8)
        for _ in range(6)
    )
    bed = np.asarray(babble, dtype=np.float32) / 6**0.5
    t = np.arange(round(0.08 * SAMPLE_RATE)) / SAMPLE_RATE
    for _ in range(round(seconds / 3)):
        start = rng.integers(0, max(1, bed.size - t.size))
        clink = np.sin(2 * np.pi * rng.uniform(2_500, 4_500) * t) * np.exp(-t * 60)
        bed[start : start + t.size] += 0.9 * clink.astype(np.float32)
    return bed
