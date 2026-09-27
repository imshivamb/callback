from callback_voice.core.models.finding import Finding
from callback_voice.core.models.metric import Metric
from callback_voice.scoring.metrics.metric_result import MetricResult
from callback_voice.scoring.timeline.call_timeline import CallTimeline


def silence_handling(timeline: CallTimeline, threshold_s: float) -> MetricResult:
    """When the caller goes silent, the agent should reprompt within ``threshold_s``.

    Silence starts when the agent stops talking before the caller's deliberate
    pause. Passing needs a reprompt in time; a silence shorter than the threshold
    that the agent waits out is inconclusive, not a failure.
    """
    samples: list[float] = []
    findings: list[Finding] = []
    verdicts: list[bool] = []
    for note in (e for e in timeline.events if e.kind == "chaos" and e.chaos_type == "silence"):
        answer = next((u for u in timeline.utterances if u.chaos_id == note.chaos_id), None)
        before = [s for s in timeline.agent_speech if s.end_s <= note.t_s + 0.05]
        if not before:
            continue
        silence_start = before[-1].end_s
        caller_back = answer.speech.start_s if answer else timeline.duration_s
        reprompt = timeline.next_agent_onset(silence_start + 0.05)
        if reprompt is not None and reprompt.start_s < caller_back:
            delay = round(reprompt.start_s - silence_start, 3)
            samples.append(delay)
            verdicts.append(delay <= threshold_s)
            if delay > threshold_s:
                findings.append(
                    Finding(
                        metric="silence_reprompt",
                        t_s=silence_start,
                        end_s=reprompt.start_s,
                        message=f"The caller went quiet and the agent took {delay:.1f} s to check in (limit {threshold_s:.0f} s).",
                    )
                )
        elif caller_back - silence_start >= threshold_s:
            verdicts.append(False)
            findings.append(
                Finding(
                    metric="silence_reprompt",
                    t_s=silence_start,
                    end_s=caller_back,
                    message=f"The caller went quiet for {caller_back - silence_start:.1f} s and the agent never checked in.",
                )
            )
    worst = max(samples) if samples else None
    return MetricResult(
        metrics=[
            Metric(
                name="silence_reprompt_s",
                value=worst,
                unit="s",
                samples=samples,
                threshold=threshold_s,
                passed=all(verdicts) if verdicts else None,
            )
        ],
        findings=findings,
    )
