from typing import ClassVar

from pydantic import Field

from callback_voice.chaos.params.base import ChaosParams, TriggerKind


class DtmfParams(ChaosParams):
    """The caller presses keypad digits."""

    triggers: ClassVar[tuple[TriggerKind, ...]] = ("caller_turn", "time")

    digits: str = Field(pattern=r"^[0-9A-Da-d*#]+$")
