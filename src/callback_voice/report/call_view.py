from pathlib import Path
from typing import Any

import soundfile as sf

from callback_voice.core.models.metric import Metric
from callback_voice.core.models.thresholds import Thresholds
from callback_voice.core.models.trial_result import TrialResult
from callback_voice.core.models.turn import Turn
from callback_voice.report.encode_mp3 import encode_mp3
from callback_voice.report.waveform_peaks import waveform_peaks

_LATENCY = "response_latency_p95_s"


def call_view(trial: TrialResult, run_dir: Path, *, audio: bool) -> dict[str, Any]:
    """Everything the report draws for one call, as plain JSON-ready data.

    Speech stretches and latency times come from ``results.json`` when the run
    recorded them; older runs are re-measured from the recording with the same scorer.
    """
    view: dict[str, Any] = {
        "call_id": trial.call_id,
        "scenario_id": trial.scenario_id,
        "trial": trial.trial,
        "seed": str(trial.seed),  # 63-bit: a JS number would round it
        "passed": trial.passed,
        "error": trial.error,
        "failure_reasons": trial.failure_reasons,
        "findings": [f.model_dump() for f in trial.findings],
        "review": [r.model_dump() for r in trial.review],
        "metrics": [
            {
                k: m.model_dump()[k]
                for k in ("name", "value", "unit", "method", "threshold", "comparator", "passed")
            }
            for m in trial.metrics
        ],
    }
    call = trial.call
    if call is None:
        return view
    view |= {
        "duration_s": call.duration_s,
        "end_reason": call.end_reason,
        "chaos": _chaos(trial),
    }
    wav = run_dir / call.wav_path
    latency = trial.metric(_LATENCY)
    speech, latency_points, remeasured = call.speech, _points(latency), False
    if wav.is_file() and (not speech or (latency and latency.samples and not latency_points)):
        speech, latency_points = _remeasure(wav.parent, trial)
        remeasured = True
    view |= {
        "speech": [_turn(t) for t in speech],
        "latency": latency_points,
        "latency_limit": latency.threshold if latency else None,
        "remeasured": remeasured,
    }
    if wav.is_file():
        samples, rate = sf.read(wav, dtype="float32", always_2d=True)
        view["peaks"] = {
            "caller": waveform_peaks(samples[:, 0], rate),
            "agent": waveform_peaks(samples[:, -1], rate),
        }
        view["audio_s"] = round(samples.shape[0] / rate, 3)
        if audio:
            view["audio"] = encode_mp3(samples, rate)
    return view


def _points(metric: Metric | None) -> list[dict[str, float]]:
    if metric is None or len(metric.sample_times_s) != len(metric.samples):
        return []
    return [{"t": t, "v": v} for t, v in zip(metric.sample_times_s, metric.samples, strict=True)]


def _remeasure(call_dir: Path, trial: TrialResult) -> tuple[list[Turn], list[dict[str, float]]]:
    from callback_voice.providers.vad.silero_vad import SileroVad
    from callback_voice.scoring.score_call import score_call
    from callback_voice.scoring.timeline.speech_turns import speech_turns

    latency = trial.metric(_LATENCY)
    limit = (
        latency.threshold if latency and latency.threshold else Thresholds().response_latency_p95_s
    )
    score = score_call(call_dir, Thresholds(response_latency_p95_s=limit), SileroVad())
    transcript = trial.call.transcript if trial.call else []
    rescored = next((m for m in score.metrics if m.name == _LATENCY), None)
    return speech_turns(score.timeline, transcript), _points(rescored)


def _turn(t: Turn) -> dict[str, Any]:
    return {"who": t.speaker, "start": t.start_s, "end": t.end_s, "text": t.text}


def _chaos(trial: TrialResult) -> list[dict[str, Any]]:
    """One marker per chaos action: timed caller-side events and line impairments."""
    assert trial.call is not None
    marks: list[dict[str, Any]] = []
    for e in trial.call.events:
        if e.chaos_type is None or e.kind not in ("chaos", "caller_utterance", "dtmf"):
            continue
        if e.kind == "caller_utterance" and e.data.get("tag") == "line":
            continue  # an ordinary line that a chaos event only delayed or rewrote
        marks.append(
            {
                "t": e.t_s,
                "end": e.end_s,
                "type": e.chaos_type,
                "id": e.chaos_id,
                "text": e.text,
                "phase": e.data.get("phase"),
                "data": {k: v for k, v in e.data.items() if k not in ("tag", "caller_timing")},
            }
        )
    return marks
