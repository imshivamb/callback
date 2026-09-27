from typing import Literal

from callback_voice.core.models.strict_model import RecordModel


class BaselineDiff(RecordModel):
    """How one aggregate moved against the stored baseline.

    ``regressed`` is only true when the move is worse, beyond noise (the 95%
    intervals do not overlap) and at least ``min_effect`` in size.
    """

    scenario_id: str
    metric: str
    baseline: float | None
    current: float | None
    delta: float | None
    baseline_ci: tuple[float, float] | None = None
    current_ci: tuple[float, float] | None = None
    min_effect: float = 0.0
    direction: Literal["better", "worse", "same", "new", "missing"]
    regressed: bool
