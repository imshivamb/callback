import numpy as np

from callback_voice.core.seeds.derive_seed import derive_seed


def make_rng(seed: int, *stream: object) -> np.random.Generator:
    """A generator for one named stream of a call (e.g. ``make_rng(seed, "chaos", event_id)``).

    Independent streams keep one feature's randomness from shifting another's when a
    scenario is edited.
    """
    return np.random.default_rng(derive_seed(seed, *stream) if stream else seed)
