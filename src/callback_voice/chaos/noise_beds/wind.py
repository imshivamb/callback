import numpy as np

from callback_voice.audio.format import Audio
from callback_voice.chaos.noise_beds.shaped_noise import envelope, shaped_noise


def wind(rng: np.random.Generator, seconds: float) -> Audio:
    """Low, gusty buffeting, like a phone held outdoors."""
    return shaped_noise(rng, seconds, slope=2.2, high_hz=1_200) * envelope(rng, seconds, 0.5, 0.9)
