from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Segment:
    """A half-open stretch of time ``[start_s, end_s)``."""

    start_s: float
    end_s: float

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s

    def contains(self, t_s: float, margin_s: float = 0.0) -> bool:
        return self.start_s - margin_s <= t_s < self.end_s + margin_s

    def overlap(self, other: "Segment") -> float:
        return max(0.0, min(self.end_s, other.end_s) - max(self.start_s, other.start_s))
