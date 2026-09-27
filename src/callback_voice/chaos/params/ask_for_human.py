from typing import ClassVar

from pydantic import Field

from callback_voice.chaos.params.base import ChaosParams, TriggerKind


class AskForHumanParams(ChaosParams):
    """The caller asks to be transferred to a person."""

    triggers: ClassVar[tuple[TriggerKind, ...]] = ("caller_turn",)

    say: str = Field(default="Can I just talk to a real person, please?", min_length=1)
