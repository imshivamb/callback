from collections.abc import Callable

import numpy as np

_RESAMPLES = 2_000
_CLUSTER_MIN_CALLS = 3


def bootstrap_interval(
    samples_per_call: list[list[float]], statistic: Callable[[np.ndarray], float], seed: int
) -> tuple[float, float] | None:
    """95% bootstrap interval for a statistic of pooled per-turn samples.

    With 3+ calls it resamples whole calls (a cluster bootstrap): turns within one call
    share an agent state and are not independent, so resampling turns would claim more
    certainty than the data has. With fewer calls it falls back to resampling turns.
    Seeded, so the same results always give the same interval.
    """
    calls = [np.asarray(s, dtype=np.float64) for s in samples_per_call if s]
    if not calls or sum(c.size for c in calls) < 2:
        return None
    rng = np.random.default_rng(seed)
    estimates = np.empty(_RESAMPLES)
    if len(calls) >= _CLUSTER_MIN_CALLS:
        for i in range(_RESAMPLES):
            picked = rng.integers(0, len(calls), len(calls))
            estimates[i] = statistic(np.concatenate([calls[j] for j in picked]))
    else:
        pooled = np.concatenate(calls)
        for i in range(_RESAMPLES):
            estimates[i] = statistic(pooled[rng.integers(0, pooled.size, pooled.size)])
    low, high = np.percentile(estimates, [2.5, 97.5])
    return float(low), float(high)
