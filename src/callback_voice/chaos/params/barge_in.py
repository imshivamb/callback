from typing import ClassVar

from pydantic import Field

from callback_voice.chaos.params.base import ChaosParams, TriggerKind


class BargeInParams(ChaosParams):
    """The caller starts talking over the agent mid-sentence."""

    triggers: ClassVar[tuple[TriggerKind, ...]] = ("agent_turn",)
    default_after_s: ClassVar[float | None] = 0.8

    say: str = Field(min_length=1)
