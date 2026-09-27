import math

from callback_voice.audio.format import Audio
from callback_voice.audio.level import rms_dbfs


class EnergyVad:
    """Level-based speech detector: deterministic and model-free.

    Used for synthetic test fixtures and as a fallback. It cannot tell speech from
    loud noise, so Silero is the default for real calls.
    """

    name = "energy"
    window_samples = 320

    def __init__(self, threshold_dbfs: float = -42.0, softness_db: float = 3.0) -> None:
        self._threshold = threshold_dbfs
        self._softness = softness_db

    def reset(self) -> None:
        """Stateless; nothing to reset."""

    def probability(self, window: Audio) -> float:
        level = rms_dbfs(window)
        return 1.0 / (1.0 + math.exp(-(level - self._threshold) / self._softness))
