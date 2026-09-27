import numpy as np

from callback_voice.audio.format import SAMPLE_RATE, Audio
from callback_voice.chaos.noise_beds.shaped_noise import envelope, shaped_noise


def street(rng: np.random.Generator, seconds: float) -> Audio:
    """Traffic rumble, passing cars and the odd distant horn."""
    rumble = shaped_noise(rng, seconds, slope=2.0, high_hz=900) * envelope(rng, seconds, 0.3, 0.6)
    hiss = shaped_noise(rng, seconds, slope=1.0, low_hz=300) * 0.35
    bed = rumble + hiss
    t = np.arange(round(0.6 * SAMPLE_RATE)) / SAMPLE_RATE
    for _ in range(max(1, round(seconds / 12))):
        start = rng.integers(0, max(1, bed.size - t.size))
        horn = (np.sin(2 * np.pi * 420 * t) + 0.6 * np.sin(2 * np.pi * 530 * t)) * np.hanning(
            t.size
        )
        bed[start : start + t.size] += 0.8 * horn.astype(np.float32)
    return bed
