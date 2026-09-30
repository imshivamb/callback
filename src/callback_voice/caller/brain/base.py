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

    timing_missing: bool
    """Replaying a recording made before line timing was saved: lines come instantly,
    so the call may differ from the original."""

    async def next_line(self, agent_said: str) -> CallerLine | None:
        """The next line, or None to hang up without speaking."""
        ...

    def note_interjection(self, text: str) -> None:
        """The caller also said ``text`` (a chaos barge-in, a changed mind)."""
        ...

    def revise_last_line(self, text: str) -> None:
        """Chaos replaced the line the brain chose; remember what was really said."""
        ...

    def apply_updates(self, updates: dict[str, Any]) -> None:
        """Merge new facts into what the caller knows (``change_mind``)."""
        ...

    def note_timing(self, think_s: float, ready_s: float) -> None:
        """How long the last line took: to decide (``think_s``, including transcribing
        the agent) and until it was ready to speak (``ready_s``). Recordings keep it."""
        ...

    def replay_ready_s(self) -> float | None:
        """When replaying: how long after planning began the last line was ready in the
        original call, so it is spoken at the same moment. None otherwise."""
        ...
