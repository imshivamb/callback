from typing import Any

from pydantic import Field, field_validator

from callback_voice.core.models.expected_fact import ExpectedFact
from callback_voice.core.models.must_not_rule import MustNotRule
from callback_voice.core.models.strict_model import StrictModel
from callback_voice.core.models.thresholds import Thresholds


class StateCheck(StrictModel):
    """Query real end state after the call and compare it with ``match``.

    ``webhook`` is a full ``http(s)://`` URL, or a path such as ``/verify`` resolved
    against the agent target's host. Callback sends a GET with ``call_id``,
    ``scenario_id`` and ``trial`` as query parameters. ``match`` keys are compared for
    equality (strings case-insensitively), except ``<field>_between: [lo, hi]`` which
    checks ``lo <= field <= hi``.
    """

    webhook: str
    match: dict[str, Any] = Field(min_length=1)
    timeout_s: float = Field(default=5.0, gt=0, le=60)

    @field_validator("webhook")
    @classmethod
    def _url_or_path(cls, value: str) -> str:
        if not value.startswith(("http://", "https://", "/")):
            raise ValueError("webhook must be an http(s):// URL or a path starting with /")
        return value


class Expectation(StrictModel):
    """How success is checked.

    ``must_not`` mixes plain-text rules (judged by the optional LLM judge,
    informational) and ``{says: <regex>}`` rules (deterministic, can fail the run).
    """

    state: StateCheck | None = None
    entities_spoken: tuple[ExpectedFact, ...] = ()
    must_not: tuple[str | MustNotRule, ...] = ()
    thresholds: Thresholds = Field(default_factory=Thresholds)
