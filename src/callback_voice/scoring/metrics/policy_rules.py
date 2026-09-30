import re

from callback_voice.core.models.finding import Finding
from callback_voice.core.models.metric import Metric
from callback_voice.core.models.must_not_rule import MustNotRule
from callback_voice.core.models.turn import Turn
from callback_voice.scoring.metrics.metric_result import MetricResult


def policy_rules(
    transcript: list[Turn], rules: list[MustNotRule], max_violations: int, *, not_checked: int = 0
) -> MetricResult:
    """Deterministic ``must_not`` checks: a regex over each agent turn's transcript.

    ``not_checked`` counts the scenario's plain-English rules that no judge looked at;
    the detail says so, so this metric never reads as if every rule passed.
    """
    if not rules:
        return MetricResult(metrics=[])
    findings = [
        Finding(
            metric="policy_violations",
            t_s=turn.start_s,
            end_s=turn.end_s,
            message=f"Policy broken ({rule.label}): the agent said “{turn.text[:120]}”.",
        )
        for rule in rules
        for turn in transcript
        if turn.speaker == "agent" and re.search(rule.says, turn.text, re.IGNORECASE)
    ]
    count = len(findings)
    return MetricResult(
        metrics=[
            Metric(
                name="policy_violations",
                value=count,
                unit="count",
                threshold=max_violations,
                passed=count <= max_violations,
                detail=f"{len(rules)} pattern rule(s) checked"
                + (f"; {not_checked} plain-English rule(s) not checked" if not_checked else ""),
            )
        ],
        findings=findings,
    )
