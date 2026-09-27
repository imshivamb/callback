import numpy as np

_BUCKETS_PER_S = 50  # 20 ms per bucket: finer than a syllable, a few KB per minute
_MAX_BUCKETS = 12_000


def waveform_peaks(samples: np.ndarray, sample_rate: int) -> list[int]:
    """Peak level per 20 ms bucket, 0–100, square-root scaled so quiet speech stays visible."""
    if samples.size == 0:
        return []
    duration = samples.size / sample_rate
    buckets = int(min(_MAX_BUCKETS, max(1, round(duration * _BUCKETS_PER_S))))
    edges = np.linspace(0, samples.size, buckets + 1).astype(int)
    peaks = np.maximum.reduceat(np.abs(samples), edges[:-1])
    return [round(100 * min(1.0, float(p)) ** 0.5) for p in peaks]
