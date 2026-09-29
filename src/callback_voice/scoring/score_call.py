from dataclasses import dataclass
from pathlib import Path

from callback_voice.core.models.finding import Finding
from callback_voice.core.models.metric import Metric
from callback_voice.core.models.thresholds import Thresholds
from callback_voice.providers.vad.base import VoiceActivityModel
from callback_voice.recording.event_log import EventLog
from callback_voice.scoring.load_call_audio import load_call_audio
from callback_voice.scoring.metrics.call_shape import call_shape
from callback_voice.scoring.metrics.chaos_timing import chaos_timing
from callback_voice.scoring.metrics.false_yield import false_yield
from callback_voice.scoring.metrics.response_latency import response_latency
from callback_voice.scoring.metrics.silence_handling import silence_handling
from callback_voice.scoring.metrics.talk_over import talk_over
from callback_voice.scoring.metrics.time_to_yield import time_to_yield
from callback_voice.scoring.timeline.build_timeline import build_timeline
from callback_voice.scoring.timeline.call_timeline import CallTimeline


@dataclass(frozen=True, slots=True)
class CallScore:
    metrics: list[Metric]
    findings: list[Finding]
    timeline: CallTimeline

    def metric(self, name: str) -> Metric | None:
        return next((m for m in self.metrics if m.name == name), None)


def score_call(call_dir: Path, thresholds: Thresholds, vad: VoiceActivityModel) -> CallScore:
    """Score one recorded call offline from ``call.wav``, ``caller_clean.wav`` and ``events.jsonl``.

    Nothing here uses live pipeline timings, so the caller's own lag during the call
    cannot skew a metric.
    """
    audio = load_call_audio(call_dir)
    timeline = build_timeline(
        agent=audio.agent,
        caller_clean=audio.caller_clean,
        events=EventLog.load(call_dir / "events.jsonl"),
        vad=vad,
        duration_s=audio.duration_s,
    )
    results = [
        response_latency(timeline, thresholds.response_latency_p95_s, thresholds.unanswered_turns),
        time_to_yield(timeline, thresholds.time_to_yield_p95_s),
        talk_over(
            timeline,
            thresholds.talk_over_ratio,
            yield_grace_s=thresholds.talk_over_grace_s or thresholds.time_to_yield_p95_s,
        ),
        false_yield(timeline, thresholds.false_yields),
        silence_handling(timeline, thresholds.silence_reprompt_s),
        chaos_timing(timeline, thresholds.chaos_drift_s),
        call_shape(timeline),
    ]
    findings = sorted((f for r in results for f in r.findings), key=lambda f: f.t_s)
    return CallScore([m for r in results for m in r.metrics], findings, timeline)
