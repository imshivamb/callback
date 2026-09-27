from typing import Any, ClassVar

from pydantic import Field

from callback_voice.chaos.params.base import ChaosParams, TriggerKind


class ChangeMindParams(ChaosParams):
    """The caller changes a detail of the request mid-call.

    ``updates`` is merged into what the caller knows so the persona stays consistent
    with the change for the rest of the call.
    """

    triggers: ClassVar[tuple[TriggerKind, ...]] = ("caller_turn",)

    say: str = Field(min_length=1)
    updates: dict[str, Any] = Field(default_factory=dict)
