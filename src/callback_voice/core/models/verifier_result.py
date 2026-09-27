from typing import Any

from pydantic import Field

from callback_voice.core.models.metric import MetricMethod
from callback_voice.core.models.strict_model import RecordModel


class VerifierResult(RecordModel):
    """Outcome of an end-state or content check. ``passed`` is None when skipped."""

    name: str
    passed: bool | None
    method: MetricMethod = "deterministic"
    detail: str
    observed: dict[str, Any] = Field(default_factory=dict)
