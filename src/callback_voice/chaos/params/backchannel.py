from typing import ClassVar

from pydantic import Field, field_validator

from callback_voice.chaos.params.base import ChaosParams, TriggerKind


class BackchannelParams(ChaosParams):
    """A short acknowledgement ("mm-hmm") the agent should talk straight through."""

    triggers: ClassVar[tuple[TriggerKind, ...]] = ("agent_turn",)
    default_after_s: ClassVar[float | None] = 1.2

    say: tuple[str, ...] = Field(default=("mm-hmm",), min_length=1)

    @field_validator("say", mode="before")
    @classmethod
    def _one_or_many(cls, value: object) -> object:
        return (value,) if isinstance(value, str) else value
