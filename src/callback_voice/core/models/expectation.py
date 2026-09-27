from typing import Any

from pydantic import AnyHttpUrl, Field

from callback_voice.core.models.strict_model import StrictModel
from callback_voice.core.models.thresholds import Thresholds


class StateCheck(StrictModel):
    """Query real end state after the call and compare it with ``match``.

    ``match`` keys are compared for equality, except ``<field>_between: [lo, hi]``
    which checks ``lo <= field <= hi``.
    """

    webhook: AnyHttpUrl
    match: dict[str, Any] = Field(min_length=1)
    timeout_s: float = Field(default=5.0, gt=0, le=60)


class Expectation(StrictModel):
    """How success is checked."""

    state: StateCheck | None = None
    entities_spoken: tuple[str, ...] = ()
    must_not: tuple[str, ...] = ()
    thresholds: Thresholds = Field(default_factory=Thresholds)
