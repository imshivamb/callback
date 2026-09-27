from dataclasses import dataclass, field
from typing import Literal

type Stage = Literal[
    "intent",
    "ref",
    "new_time",
    "choose_slot",
    "confirm_move",
    "confirm_cancel",
    "new_name",
    "new_details",
    "confirm_new",
    "anything_else",
    "done",
]


@dataclass(slots=True)
class DialogState:
    """Slots gathered so far and where the conversation is."""

    stage: Stage = "intent"
    intent: Literal["move", "new", "cancel", "check"] | None = None
    ref: str | None = None
    day: str | None = None
    hour: int | None = None
    minute: int = 0
    earliest: int | None = None
    latest: int | None = None
    party_size: int | None = None
    name: str | None = None
    window_seat: bool = False
    offered: list[tuple[int, int]] = field(default_factory=list)
    misunderstood: int = 0
    last_reply: str = ""
