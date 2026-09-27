from typing import ClassVar

from pydantic import Field

from callback_voice.chaos.params.base import ChaosParams, TriggerKind


class RepeatRequestParams(ChaosParams):
    """The caller did not catch that and asks the agent to repeat itself."""

    triggers: ClassVar[tuple[TriggerKind, ...]] = ("caller_turn",)

    say: str = Field(default="Sorry, I didn't catch that. Can you say it again?", min_length=1)
