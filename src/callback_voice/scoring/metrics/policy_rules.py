import re

from callback_voice.core.models.finding import Finding
from callback_voice.core.models.metric import Metric
from callback_voice.core.models.must_not_rule import MustNotRule
from callback_voice.core.models.turn import Turn
from callback_voice.scoring.metrics.metric_result import MetricResult


def policy_rules(
    transcript: list[Turn], rules: list[MustNotRule], max_violations: int
) -> MetricResult:
    """Deterministic ``must_not`` checks: a regex over each agent turn's transcript."""
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
                detail=f"{len(rules)} rule(s) checked",
            )
        ],
        findings=findings,
    )
