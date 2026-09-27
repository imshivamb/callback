from callback_voice.core.models.finding import Finding
from callback_voice.core.models.metric import Metric
from callback_voice.scoring.metrics.metric_result import MetricResult
from callback_voice.scoring.timeline.call_timeline import CallTimeline
from callback_voice.scoring.timeline.interval_ops import intersect, subtract, total
from callback_voice.scoring.timeline.segment import Segment

_REPORT_OVERLAP_S = 0.3


def talk_over(timeline: CallTimeline, threshold_ratio: float, yield_grace_s: float) -> MetricResult:
    """Share of the caller's speech that the agent talked over.

    Deliberate overlaps are excused: backchannels (meant to overlap), and the first
    ``yield_grace_s`` whenever the caller cuts in (the agent may take that long to stop).
    """
    excused = [u.speech for u in timeline.utterances if u.tag in {"backchannel", "dtmf"}]
    # Whenever the caller starts talking over the agent (a barge-in or not), the agent
    # gets the yield budget to stop before the overlap counts against it.
    excused += [
        Segment(u.speech.start_s, u.speech.start_s + yield_grace_s)
        for u in timeline.utterances
        if timeline.agent_speaking_at(u.speech.start_s, margin_s=0.05) is not None
    ]
    caller = subtract(timeline.caller_speech, excused)
    overlaps = intersect(caller, timeline.agent_speech)
    spoken = total(caller)
    ratio = total(overlaps) / spoken if spoken > 0 else None
    findings = [
        Finding(
            metric="talk_over",
            t_s=o.start_s,
            end_s=o.end_s,
            message=f"The agent talked over the caller for {o.duration_s:.2f} s.",
        )
        for o in overlaps
        if o.duration_s >= _REPORT_OVERLAP_S
    ]
    return MetricResult(
        metrics=[
            Metric(
                name="talk_over_ratio",
                value=None if ratio is None else round(ratio, 4),
                unit="ratio",
                threshold=threshold_ratio,
                passed=None if ratio is None else ratio <= threshold_ratio,
            )
        ],
        findings=findings,
    )
