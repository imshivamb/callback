from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class CallerLine:
    """What the caller says next. ``hang_up`` ends the call after it is spoken."""

    text: str
    hang_up: bool = False
    goal_reached: bool = False


class CallerBrain(Protocol):
    """Decides the caller's next line from what the agent just said."""

    needs_agent_text: bool
    """False for scripted callers, which saves transcribing the agent live."""

    async def next_line(self, agent_said: str) -> CallerLine | None:
        """The next line, or None to hang up without speaking."""
        ...

    def note_interjection(self, text: str) -> None:
        """The caller also said ``text`` (a chaos barge-in, a changed mind)."""
        ...

    def apply_updates(self, updates: dict[str, Any]) -> None:
        """Merge new facts into what the caller knows (``change_mind``)."""
        ...
