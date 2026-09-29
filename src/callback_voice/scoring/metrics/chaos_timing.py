from callback_voice.core.models.finding import Finding
from callback_voice.core.models.metric import Metric
from callback_voice.scoring.metrics.metric_result import MetricResult
from callback_voice.scoring.timeline.call_timeline import CallTimeline


def chaos_timing(timeline: CallTimeline, drift_limit_s: float = 0.1) -> MetricResult:
    """How late chaos actions hit the wire versus when they were scheduled.

    This checks Callback itself, not the agent: drift over ``drift_limit_s`` (100 ms by
    default) means the caller pipeline lagged and the chaos did not land where the
    scenario asked. Informational: it never fails a run.
    """
    drifts = [
        (u, u.planned.start_s - e.intended_s)
        for e in timeline.events
        if e.kind == "caller_utterance" and e.intended_s is not None
        for u in timeline.utterances
        if u.planned.start_s == e.t_s
    ]
    findings = [
        Finding(
            metric="chaos_timing",
            t_s=u.planned.start_s,
            severity="warn",
            chaos_id=u.chaos_id,
            message=f"Chaos {u.chaos_type} landed {d * 1000:.0f} ms late; timing-sensitive results may be off.",
        )
        for u, d in drifts
        if d > drift_limit_s
    ]
    worst = max((d for _, d in drifts), default=None)
    return MetricResult(
        metrics=[
            Metric(
                name="chaos_drift_max_s",
                value=None if worst is None else round(worst, 3),
                unit="s",
                threshold=drift_limit_s,
                detail="Callback self-check; informational",
            )
        ],
        findings=findings,
    )
