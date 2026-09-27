from dataclasses import dataclass
from typing import Literal

type RunKind = Literal["turn", "ignored", "unheard"]


@dataclass(slots=True)
class CallerTurnTracker:
    """Tracks the caller's current turn on the inbound stream clock.

    A speech run is a ``turn`` (the caller is talking to the agent), ``ignored``
    (judged a backchannel while the agent spoke) or ``unheard`` (arrived while the
    agent's mic was muted). Only turns get answered.
    """

    end_of_turn_s: float
    turn_start: float | None = None
    pending_end: float | None = None
    run_kind: RunKind = "turn"
    run_start: float = 0.0

    def on_speech_start(self, t_s: float, kind: RunKind) -> None:
        self.run_start, self.run_kind = t_s, kind
        if kind == "turn":
            self.pending_end = None
            if self.turn_start is None:
                self.turn_start = t_s

    def promote_run(self) -> None:
        """An ignored/unheard run turned out to be a real interruption."""
        self.run_kind = "turn"
        self.pending_end = None
        if self.turn_start is None:
            self.turn_start = self.run_start

    def on_speech_end(self, t_s: float) -> None:
        if self.run_kind == "turn" and self.turn_start is not None:
            self.pending_end = t_s

    def turn_complete(self, now_s: float, caller_speaking: bool) -> tuple[float, float] | None:
        """``(start, end)`` of a finished turn once the caller has been quiet long enough."""
        if self.pending_end is None or self.turn_start is None or caller_speaking:
            return None
        if now_s - self.pending_end < self.end_of_turn_s:
            return None
        span = (self.turn_start, self.pending_end)
        self.turn_start = self.pending_end = None
        return span

    @property
    def mid_turn(self) -> bool:
        return self.turn_start is not None
