from pydantic import Field

from callback_voice.chaos.params.base import ChaosParams


class NoiseParams(ChaosParams):
    """A background noise bed mixed under the caller's voice for the whole call.

    ``bed`` is a built-in procedural bed (street, cafe, office, wind, hum) or a path
    to an audio file you are licensed to use.
    """

    bed: str = "street"
    snr_db: float = Field(default=15.0, ge=-5, le=60)
