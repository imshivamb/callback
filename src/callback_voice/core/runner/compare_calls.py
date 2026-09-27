from dataclasses import dataclass

from callback_voice.core.models.call_event import CallEvent


@dataclass(frozen=True, slots=True)
class Reproduction:
    lines_match: bool
    chaos_match: bool
    original_lines: list[str]
    replayed_lines: list[str]
    original_chaos: list[str]
    replayed_chaos: list[str]

    @property
    def exact(self) -> bool:
        return self.lines_match and self.chaos_match


def compare_calls(original: list[CallEvent], replayed: list[CallEvent]) -> Reproduction:
    """Did a replay reproduce the call: same caller lines, same chaos decisions?

    Chaos decisions are compared by what fired and what was said (phrase choices,
    which turns), not by absolute clock time, which follows the agent's own timing.
    """

    def lines(events: list[CallEvent]) -> list[str]:
        return [
            e.text or ""
            for e in events
            if e.kind == "caller_utterance" and e.data.get("tag") == "line"
        ]

    def chaos(events: list[CallEvent]) -> list[str]:
        acted = [
            f"{e.chaos_id}: {e.text}" for e in events if e.kind == "caller_utterance" and e.chaos_id
        ]
        return acted + sorted(f"{e.chaos_id}" for e in events if e.kind == "chaos")

    a, b = lines(original), lines(replayed)
    c, d = chaos(original), chaos(replayed)
    return Reproduction(a == b, c == d, a, b, c, d)
