"""The one internal audio format."""

from typing import Final

import numpy as np
from numpy.typing import NDArray

SAMPLE_RATE: Final = 16_000
FRAME_MS: Final = 20
FRAME_SAMPLES: Final = SAMPLE_RATE * FRAME_MS // 1000
FRAME_S: Final = FRAME_MS / 1000

type Audio = NDArray[np.float32]


def silence(seconds: float) -> Audio:
    """Return ``seconds`` of digital silence."""
    return np.zeros(round(seconds * SAMPLE_RATE), dtype=np.float32)
