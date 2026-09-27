from pydantic import Field, model_validator

from callback_voice.chaos.params.base import TriggerKind
from callback_voice.core.models.strict_model import StrictModel


class ChaosTrigger(StrictModel):
    """When an event fires.

    ``turn`` targets one turn (1-based); ``every`` targets every Nth turn. ``after_s``
    is the offset into an agent turn; ``at_s`` is an absolute call time.
    """

    on: TriggerKind
    turn: int | None = Field(default=None, ge=1)
    every: int | None = Field(default=None, ge=1)
    after_s: float | None = Field(default=None, ge=0)
    at_s: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _consistent(self) -> "ChaosTrigger":
        if self.on == "time":
            if self.at_s is None:
                raise ValueError("on: time needs at_s")
            if self.turn is not None or self.every is not None:
                raise ValueError("on: time takes at_s, not turn/every")
        else:
            if (self.turn is None) == (self.every is None):
                raise ValueError(f"on: {self.on} needs exactly one of turn or every")
            if self.at_s is not None:
                raise ValueError(f"on: {self.on} takes turn/every, not at_s")
        if self.after_s is not None and self.on != "agent_turn":
            raise ValueError("after_s only applies to on: agent_turn")
        return self

    def matches_turn(self, turn: int) -> bool:
        """Whether this trigger targets the given 1-based turn number."""
        if self.turn is not None:
            return turn == self.turn
        return self.every is not None and turn % self.every == 0
