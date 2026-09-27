"""Shared base for chaos parameter models."""

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict

type TriggerKind = Literal["agent_turn", "caller_turn", "time"]


class ChaosParams(BaseModel):
    """Parameters of one chaos event.

    ``triggers`` lists which ``on:`` values the event accepts; an empty tuple means
    the event is a time window or a continuous effect and takes no trigger.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    triggers: ClassVar[tuple[TriggerKind, ...]] = ()
    default_after_s: ClassVar[float | None] = None
