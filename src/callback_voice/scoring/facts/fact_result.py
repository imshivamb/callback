from dataclasses import dataclass
from typing import Literal

from callback_voice.core.models.expected_fact import ExpectedFact

type FactStatus = Literal["correct", "wrong", "missing", "uncertain"]


@dataclass(frozen=True, slots=True)
class FactResult:
    """The verdict on one expected fact, with where it was (or should have been) said."""

    fact: ExpectedFact
    status: FactStatus
    heard: str | None
    t_s: float
    end_s: float | None
    reason: str
