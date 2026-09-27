from math import sqrt

_Z95 = 1.959964


def wilson_interval(successes: int, trials: int) -> tuple[float, float] | None:
    """95% Wilson score interval for a success rate; None for zero trials.

    Unlike the plain normal approximation, it stays inside [0, 1] and behaves at small n
    and at 0% or 100%, which is exactly where voice-agent suites live (3–20 trials).
    """
    if trials <= 0:
        return None
    p = successes / trials
    z2 = _Z95**2
    centre = (p + z2 / (2 * trials)) / (1 + z2 / trials)
    half = _Z95 * sqrt(p * (1 - p) / trials + z2 / (4 * trials**2)) / (1 + z2 / trials)
    return max(0.0, centre - half), min(1.0, centre + half)
