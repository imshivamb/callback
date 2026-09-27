from callback_voice.core.models.metric import Metric
from callback_voice.scoring.metrics.metric_result import MetricResult
from callback_voice.scoring.timeline.call_timeline import CallTimeline


def call_shape(timeline: CallTimeline) -> MetricResult:
    """Informational: how long the call ran and how many turns each side took."""
    agent_turns = sum(1 for e in timeline.events if e.kind == "agent_turn_start")
    caller_turns = sum(1 for u in timeline.utterances if u.takes_floor)
    return MetricResult(
        metrics=[
            Metric(name="call_duration_s", value=round(timeline.duration_s, 2), unit="s"),
            Metric(name="caller_turns", value=caller_turns, unit="count"),
            Metric(name="agent_turns", value=agent_turns, unit="count"),
        ]
    )
