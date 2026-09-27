from typing import Literal

from pydantic import Field

from callback_voice.core.models.strict_model import RecordModel

type MetricMethod = Literal["deterministic", "judge"]
type Comparator = Literal["<=", ">="]


class Metric(RecordModel):
    """One measured quantity for one call.

    ``passed`` is None when the metric is informational or could not be computed
    (for example no barge-ins happened, so there is no time-to-yield). Only
    deterministic metrics can fail a run by default.
    """

    name: str
    value: float | None
    unit: str
    method: MetricMethod = "deterministic"
    threshold: float | None = None
    comparator: Comparator = "<="
    passed: bool | None = None
    detail: str | None = None
    samples: list[float] = Field(default_factory=list)
    sample_times_s: list[float] = Field(default_factory=list)
    """Where each sample happened on the recording clock, when the metric knows."""


def judge_threshold(value: float, threshold: float, comparator: Comparator) -> bool:
    """Apply a comparator to a value and its threshold."""
    return value <= threshold if comparator == "<=" else value >= threshold
