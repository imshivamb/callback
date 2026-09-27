from callback_voice.core.models.finding import Finding
from callback_voice.core.models.metric import Metric
from callback_voice.scoring.metrics.metric_result import MetricResult
from callback_voice.scoring.timeline.call_timeline import CallTimeline

_STOP_WITHIN_S = 1.0
_SILENT_FOR_S = 0.6


def false_yield(timeline: CallTimeline, max_allowed: int) -> MetricResult:
    """The agent stopped for a backchannel it should have talked through.

    Counted when the agent goes quiet within 1 s of a "mm-hmm" and stays quiet for
    at least 0.6 s (longer than a pause between sentences).
    """
    findings: list[Finding] = []
    checked = 0
    for utt in timeline.utterances:
        if utt.tag != "backchannel":
            continue
        talking = timeline.agent_speaking_at(utt.speech.start_s, margin_s=0.05)
        if talking is None:
            continue
        checked += 1
        stopped = talking.end_s
        resumed = timeline.next_agent_onset(stopped + 0.01)
        quiet = (resumed.start_s if resumed else timeline.duration_s) - stopped
        if stopped - utt.speech.start_s <= _STOP_WITHIN_S and quiet >= _SILENT_FOR_S:
            findings.append(
                Finding(
                    metric="false_yield",
                    t_s=utt.speech.start_s,
                    end_s=stopped,
                    chaos_id=utt.chaos_id,
                    message=(
                        f"The agent stopped talking {stopped - utt.speech.start_s:.2f} s after the caller "
                        f"said “{utt.text}”, which was only an acknowledgement."
                    ),
                )
            )
    count = len(findings)
    return MetricResult(
        metrics=[
            Metric(
                name="false_yields",
                value=count if checked else None,
                unit="count",
                threshold=max_allowed,
                passed=None if not checked else count <= max_allowed,
                detail=f"{checked} backchannel(s) said while the agent was talking",
            )
        ],
        findings=findings,
    )
