from callback_voice.core.models.finding import Finding
from callback_voice.core.models.metric import Metric
from callback_voice.scoring.metrics.metric_result import MetricResult
from callback_voice.scoring.stats.percentile import percentile
from callback_voice.scoring.timeline.call_timeline import CallTimeline

_ONSET_SLACK_S = 0.02


def response_latency(timeline: CallTimeline, threshold_p95_s: float) -> MetricResult:
    """Caller stops talking -> first agent audio, for every caller turn that expects an answer.

    Turns where the agent was already talking when the caller finished are left out
    (that is talk-over, measured separately), as are turns the agent never answered
    before the caller spoke again (reported as findings).
    """
    samples: list[float] = []
    times: list[float] = []
    findings: list[Finding] = []
    floor_turns = [u for u in timeline.utterances if u.takes_floor]
    for i, utt in enumerate(floor_turns):
        end = utt.speech.end_s
        if timeline.agent_speaking_at(end - _ONSET_SLACK_S):
            continue
        reply = timeline.next_agent_onset(end - _ONSET_SLACK_S)
        next_caller = (
            floor_turns[i + 1].speech.start_s if i + 1 < len(floor_turns) else timeline.duration_s
        )
        if reply is None or reply.start_s >= next_caller:
            if i + 1 < len(floor_turns):
                findings.append(
                    Finding(
                        metric="response_latency",
                        t_s=end,
                        severity="warn",
                        message=f"The agent never answered “{_short(utt.text)}”.",
                    )
                )
            continue
        latency = max(0.0, reply.start_s - end)
        samples.append(round(latency, 3))
        times.append(round(end, 3))
        if latency > threshold_p95_s:
            findings.append(
                Finding(
                    metric="response_latency",
                    t_s=end,
                    end_s=reply.start_s,
                    message=f"The agent took {latency:.2f} s to respond (limit {threshold_p95_s:.2f} s).",
                )
            )
    p50, p95 = percentile(samples, 50), percentile(samples, 95)
    return MetricResult(
        metrics=[
            Metric(
                name="response_latency_p50_s",
                value=_r(p50),
                unit="s",
                samples=samples,
                sample_times_s=times,
            ),
            Metric(
                name="response_latency_p95_s",
                value=_r(p95),
                unit="s",
                samples=samples,
                sample_times_s=times,
                threshold=threshold_p95_s,
                passed=None if p95 is None else p95 <= threshold_p95_s,
            ),
        ],
        findings=findings,
    )


def _r(value: float | None) -> float | None:
    return None if value is None else round(value, 3)


def _short(text: str, limit: int = 48) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
