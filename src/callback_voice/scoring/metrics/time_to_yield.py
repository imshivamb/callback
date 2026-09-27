from callback_voice.core.models.finding import Finding
from callback_voice.core.models.metric import Metric
from callback_voice.scoring.metrics.metric_result import MetricResult
from callback_voice.scoring.stats.percentile import percentile
from callback_voice.scoring.timeline.call_timeline import CallTimeline
from callback_voice.scoring.timeline.interval_ops import overlapping
from callback_voice.scoring.timeline.segment import Segment


def time_to_yield(timeline: CallTimeline, threshold_p95_s: float) -> MetricResult:
    """Barge-in onset -> the agent is silent for good while the caller holds the floor.

    If the agent stops and then resumes over the caller, it has not yielded: the
    yield is measured to the end of the last agent speech that began before the
    caller finished. Barge-ins that land while the agent is already silent are
    skipped.
    """
    samples: list[float] = []
    findings: list[Finding] = []
    for utt in timeline.utterances:
        if utt.tag != "barge_in":
            continue
        onset = utt.speech.start_s
        if timeline.agent_speaking_at(onset, margin_s=0.05) is None:
            continue
        window = Segment(onset, utt.speech.end_s)
        talking = [
            s for s in overlapping(timeline.agent_speech, window) if s.start_s < utt.speech.end_s
        ]
        stopped = max((s.end_s for s in talking), default=onset)
        yield_s = round(max(0.0, stopped - onset), 3)
        samples.append(yield_s)
        if yield_s > threshold_p95_s:
            findings.append(
                Finding(
                    metric="time_to_yield",
                    t_s=onset,
                    end_s=stopped,
                    chaos_id=utt.chaos_id,
                    message=(
                        f"The caller cut in (“{utt.text}”) and the agent kept talking for "
                        f"{yield_s:.2f} s (limit {threshold_p95_s:.2f} s)."
                    ),
                )
            )
    p95 = percentile(samples, 95)
    return MetricResult(
        metrics=[
            Metric(
                name="time_to_yield_p95_s",
                value=None if p95 is None else round(p95, 3),
                unit="s",
                samples=samples,
                threshold=threshold_p95_s,
                passed=None if p95 is None else p95 <= threshold_p95_s,
            )
        ],
        findings=findings,
    )
