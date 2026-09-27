import json

from callback_voice.core.models.finding import Finding
from callback_voice.core.models.metric import Metric
from callback_voice.core.models.turn import Turn
from callback_voice.errors import ProviderError
from callback_voice.providers.llm.base import ChatModel
from callback_voice.scoring.judge.judge_prompt import judge_messages
from callback_voice.scoring.judge.parse_judge_reply import parse_judge_reply
from callback_voice.scoring.metrics.metric_result import MetricResult


async def judge_call(llm: ChatModel, transcript: list[Turn], rules: list[str]) -> MetricResult:
    """Ask the LLM judge about plain-text ``must_not`` rules and conversational quality.

    Every metric here is ``method="judge"``: shown in results, never failing a run by
    default. A judge that errors or returns junk is recorded as a warning, not a crash.
    """
    try:
        completion = await llm.complete(
            judge_messages(transcript, rules), temperature=0.0, max_tokens=800, json_mode=True
        )
        verdict = parse_judge_reply(completion.text)
    except (ProviderError, ValueError, json.JSONDecodeError) as exc:
        return MetricResult(
            metrics=[],
            findings=[
                Finding(
                    metric="judge",
                    t_s=0.0,
                    severity="warn",
                    message=f"The LLM judge could not score this call: {exc}",
                )
            ],
        )
    violated = [r for r in verdict.rules if r.violated]
    metrics = []
    if rules:
        metrics.append(
            Metric(
                name="policy_violations_judged",
                value=len(violated),
                unit="count",
                method="judge",
                detail=f"{len(rules)} plain-text rule(s) judged",
            )
        )
    for key, score in verdict.experience.items():
        metrics.append(
            Metric(
                name=f"experience_{key}",
                value=score,
                unit="score",
                method="judge",
                detail=verdict.summary or None,
            )
        )
    findings = [
        Finding(
            metric="policy_violations_judged",
            t_s=r.at_s or 0.0,
            severity="warn",
            message=f"The judge thinks the agent broke “{r.rule}”: “{r.evidence[:120]}”.",
        )
        for r in violated
    ]
    return MetricResult(metrics=metrics, findings=findings)
