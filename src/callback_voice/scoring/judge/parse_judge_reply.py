import json
import re
from dataclasses import dataclass, field
from typing import Any

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class RuleVerdict:
    rule: str
    violated: bool
    evidence: str
    at_s: float | None


@dataclass(frozen=True, slots=True)
class JudgeVerdict:
    rules: list[RuleVerdict] = field(default_factory=list)
    experience: dict[str, float] = field(default_factory=dict)
    summary: str = ""


def parse_judge_reply(raw: str) -> JudgeVerdict:
    """Read the judge's JSON, tolerating code fences; scores are clamped to 1..5."""
    text = _FENCE.sub("", raw.strip())
    data: Any = json.loads(text[text.find("{") : text.rfind("}") + 1])
    rules = [
        RuleVerdict(
            str(r.get("rule", "")),
            bool(r.get("violated", False)),
            str(r.get("evidence", "")),
            float(r["at_s"]) if isinstance(r.get("at_s"), int | float) else None,
        )
        for r in data.get("rules", [])
        if isinstance(r, dict)
    ]
    experience_raw = data.get("experience", {}) or {}
    experience = {
        key: float(min(5, max(1, experience_raw[key])))
        for key in ("concise", "no_repetition", "handles_frustration")
        if isinstance(experience_raw.get(key), int | float)
    }
    return JudgeVerdict(rules, experience, str(experience_raw.get("summary", "")))
