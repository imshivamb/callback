from typing import ClassVar

from pydantic import Field

from callback_voice.chaos.params.base import ChaosParams, TriggerKind


class RateChangeParams(ChaosParams):
    """From the triggering caller turn on, the caller speaks faster or slower."""

    triggers: ClassVar[tuple[TriggerKind, ...]] = ("caller_turn",)

    rate: float = Field(gt=0.5, le=2.0)
