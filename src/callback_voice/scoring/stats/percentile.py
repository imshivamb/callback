import numpy as np


def percentile(values: list[float], q: float) -> float | None:
    """Linear-interpolated percentile (``q`` in 0..100); None for no values."""
    if not values:
        return None
    return float(np.percentile(np.asarray(values, dtype=np.float64), q))
