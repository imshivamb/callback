from callback_voice.core.models.finding import Finding
from callback_voice.core.models.metric import Metric
from callback_voice.scoring.facts.fact_result import FactResult
from callback_voice.scoring.metrics.metric_result import MetricResult


def entity_fidelity(results: list[FactResult], threshold: float) -> MetricResult:
    """Share of settled facts the agent said correctly. Uncertain facts are left out
    (they go to review) so a transcription mistake cannot fail the agent.
    """
    if not results:
        return MetricResult(metrics=[])
    settled = [r for r in results if r.status != "uncertain"]
    correct = sum(r.status == "correct" for r in settled)
    uncertain = len(results) - len(settled)
    findings: list[Finding] = []
    for r in results:
        if r.status == "wrong":
            findings.append(
                Finding(
                    metric="entity_fidelity",
                    t_s=r.t_s,
                    end_s=r.end_s,
                    message=f"The agent said “{r.heard}” instead of “{_spoken(r)}” ({r.fact.name}).",
                )
            )
        elif r.status == "missing":
            findings.append(
                Finding(
                    metric="entity_fidelity",
                    t_s=r.t_s,
                    message=f"The agent never said {r.fact.name} (“{r.fact.value}”).",
                )
            )
        elif r.status == "uncertain":
            findings.append(
                Finding(
                    metric="entity_fidelity",
                    t_s=r.t_s,
                    end_s=r.end_s,
                    severity="warn",
                    message=f"Uncertain, review: {r.fact.name}: {r.reason}.",
                )
            )
    value = round(correct / len(settled), 3) if settled else None
    detail = f"{correct}/{len(settled)} facts correct" + (
        f"; {uncertain} uncertain (review)" if uncertain else ""
    )
    return MetricResult(
        metrics=[
            Metric(
                name="entity_fidelity",
                value=value,
                unit="ratio",
                threshold=threshold,
                comparator=">=",
                passed=None if value is None else value >= threshold,
                detail=detail,
            ),
            Metric(
                name="facts_uncertain",
                value=uncertain,
                unit="count",
                detail="needs a person to listen",
            ),
        ],
        findings=findings,
    )


def _spoken(result: FactResult) -> str:
    value = result.fact.value
    return " ".join(value) if result.fact.kind == "code" else value
