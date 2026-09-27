from typing import ClassVar

from pydantic import Field

from callback_voice.chaos.params.base import ChaosParams, TriggerKind


class SilenceParams(ChaosParams):
    """The caller goes quiet instead of answering; the agent should reprompt."""

    triggers: ClassVar[tuple[TriggerKind, ...]] = ("caller_turn",)

    duration_s: float = Field(default=6.0, gt=0, le=60)
