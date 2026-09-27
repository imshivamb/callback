from callback_voice.core.models.finding import Finding
from callback_voice.core.models.metric import Metric
from callback_voice.core.models.verifier_result import VerifierResult
from callback_voice.scoring.metrics.metric_result import MetricResult


def task_success(
    result: VerifierResult | None, threshold_rate: float, call_end_s: float
) -> MetricResult:
    """1 if the real end state matched the scenario, 0 if not.

    Per call this passes only at 1; across trials the threshold applies to the rate.
    """
    if result is None:
        return MetricResult(metrics=[])
    value = 1.0 if result.passed else 0.0
    findings = (
        []
        if result.passed
        else [
            Finding(
                metric="task_success",
                t_s=call_end_s,
                message=f"The task was not done: {result.detail}.",
            )
        ]
    )
    return MetricResult(
        metrics=[
            Metric(
                name="task_success",
                value=value,
                unit="ratio",
                threshold=threshold_rate,
                comparator=">=",
                passed=value >= threshold_rate,
                detail=result.detail,
            )
        ],
        findings=findings,
    )
