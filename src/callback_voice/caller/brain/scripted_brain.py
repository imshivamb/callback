from typing import Any

from callback_voice.caller.brain.base import CallerLine


class ScriptedBrain:
    """Says a fixed list of lines in order, one per agent turn. Needs no LLM.

    The last line hangs up. Deterministic by construction, which makes scripted
    callers the right choice for demos and for testing the agent's audio behaviour
    rather than its dialogue.
    """

    needs_agent_text = False
    timing_missing = False

    def __init__(self, script: tuple[str, ...]) -> None:
        self._script = list(script)
        self._next = 0

    async def next_line(self, agent_said: str) -> CallerLine | None:
        if self._next >= len(self._script):
            return None
        text = self._script[self._next]
        self._next += 1
        last = self._next == len(self._script)
        return CallerLine(text, hang_up=last, goal_reached=last)

    def note_interjection(self, text: str) -> None:
        """Scripted callers do not adapt to interjections."""

    def revise_last_line(self, text: str) -> None:
        """Scripted callers keep their script."""

    def apply_updates(self, updates: dict[str, Any]) -> None:
        """Scripted callers do not adapt to changed facts."""

    def note_timing(self, think_s: float, ready_s: float) -> None:
        """Only recordings keep line timing."""

    def replay_ready_s(self) -> float | None:
        return None
