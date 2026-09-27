from typing import Literal

from callback_voice.core.models.strict_model import RecordModel


class BaselineDiff(RecordModel):
    """How one aggregate moved against the stored baseline.

    ``regressed`` is only true when the move is beyond noise: the intervals do not
    overlap, or the change exceeds the configured minimum effect.
    """

    scenario_id: str
    metric: str
    baseline: float | None
    current: float | None
    delta: float | None
    direction: Literal["better", "worse", "same", "new", "missing"]
    regressed: bool
