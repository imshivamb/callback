import numpy as np

from callback_voice.audio.format import SAMPLE_RATE, Audio


def shaped_noise(
    rng: np.random.Generator,
    seconds: float,
    *,
    slope: float,
    low_hz: float = 20.0,
    high_hz: float = 7_500.0,
) -> Audio:
    """Noise whose power falls off as 1/f**slope (0 white, 1 pink, 2 brown), band-limited.

    Built in the frequency domain, so it is exact and fast for multi-second beds.
    Returned at unit RMS.
    """
    n = round(seconds * SAMPLE_RATE)
    spectrum = rng.normal(size=n // 2 + 1) + 1j * rng.normal(size=n // 2 + 1)
    freqs = np.fft.rfftfreq(n, 1 / SAMPLE_RATE)
    gain = np.zeros_like(freqs)
    band = (freqs >= low_hz) & (freqs <= high_hz)
    gain[band] = freqs[band] ** (-slope / 2)
    audio = np.fft.irfft(spectrum * gain, n)
    unit: Audio = (audio / (np.sqrt(np.mean(audio**2)) + 1e-12)).astype(np.float32)
    return unit


def envelope(rng: np.random.Generator, seconds: float, rate_hz: float, depth: float) -> Audio:
    """A smooth random amplitude envelope in [1 - depth, 1] changing about ``rate_hz`` times a second."""
    points = max(2, round(seconds * rate_hz) + 2)
    knots = 1 - depth * rng.random(points)
    curve: Audio = np.interp(
        np.linspace(0, points - 1, round(seconds * SAMPLE_RATE)), np.arange(points), knots
    ).astype(np.float32)
    return curve
