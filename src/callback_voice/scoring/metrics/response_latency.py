from callback_voice.core.models.finding import Finding
from callback_voice.core.models.metric import Metric
from callback_voice.scoring.metrics.metric_result import MetricResult
from callback_voice.scoring.stats.percentile import percentile
from callback_voice.scoring.timeline.call_timeline import CallTimeline
from callback_voice.scoring.timeline.segment import Segment

_ONSET_SLACK_S = 0.02


def response_latency(
    timeline: CallTimeline, threshold_p95_s: float, max_unanswered: int = 0
) -> MetricResult:
    """Caller stops talking -> first agent audio, for every caller turn that expects an answer.

    Turns where the agent was already talking when the caller finished are left out
    (that is talk-over, measured separately). A turn the agent never answered is an
    *unanswered turn* only if the caller then waited at least the latency limit before
    speaking again: a caller who goes straight on to the next sentence gave the agent no
    opening, and that is not the agent's fault. A turn the agent talked over to the
    end is judged from when the agent stopped talking.
    """
    samples: list[float] = []
    times: list[float] = []
    unanswered = 0
    findings: list[Finding] = []
    floor_turns = [u for u in timeline.utterances if u.takes_floor]
    for i, utt in enumerate(floor_turns):
        end = utt.speech.end_s
        next_caller = (
            floor_turns[i + 1].speech.start_s if i + 1 < len(floor_turns) else timeline.duration_s
        )
        talking = timeline.agent_speaking_at(end - _ONSET_SLACK_S)
        if talking is not None:
            # Talked over to the end (talk-over is measured separately, so no latency
            # sample). The agent's chance to answer starts when it stops talking.
            stopped = _end_of_speech_run(timeline, talking)
            reply = timeline.next_agent_onset(stopped + _ONSET_SLACK_S)
            waited = next_caller - stopped
            if (
                i + 1 < len(floor_turns)
                and (reply is None or reply.start_s >= next_caller)
                and waited >= threshold_p95_s
            ):
                unanswered += 1
                findings.append(
                    Finding(
                        metric="unanswered_turns",
                        t_s=end,
                        end_s=next_caller,
                        message=(
                            f"The agent talked over “{_short(utt.text)}”, stopped, and never "
                            f"answered it; the caller waited {waited:.1f} s."
                        ),
                    )
                )
            continue
        reply = timeline.next_agent_onset(end - _ONSET_SLACK_S)
        if reply is None or reply.start_s >= next_caller:
            waited = next_caller - end
            if i + 1 < len(floor_turns) and waited >= threshold_p95_s:
                unanswered += 1
                findings.append(
                    Finding(
                        metric="unanswered_turns",
                        t_s=end,
                        end_s=next_caller,
                        message=(
                            f"The caller waited {waited:.1f} s and the agent never answered "
                            f"“{_short(utt.text)}”."
                        ),
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
            Metric(
                name="unanswered_turns",
                value=unanswered,
                unit="count",
                threshold=max_unanswered,
                passed=unanswered <= max_unanswered,
            ),
        ],
        findings=findings,
    )


_SAME_RUN_GAP_S = 1.0
"""Agent speech closer together than this is one run (pauses between sentences)."""


def _end_of_speech_run(timeline: CallTimeline, segment: Segment) -> float:
    """Where the agent's continuous speech that includes ``segment`` ends."""
    end = segment.end_s
    for s in timeline.agent_speech:
        if s.start_s > end + _SAME_RUN_GAP_S:
            break
        if s.start_s >= segment.start_s:
            end = max(end, s.end_s)
    return end


def _r(value: float | None) -> float | None:
    return None if value is None else round(value, 3)


def _short(text: str, limit: int = 48) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
