"""M3 gate: synthetic calls with known timings must score within ±50 ms."""

import json
from pathlib import Path

import pytest

from callback_voice.core.models.thresholds import Thresholds
from callback_voice.providers.vad.silero_vad import SileroVad
from callback_voice.scoring.score_call import score_call

CALLS = Path(__file__).parents[1] / "fixtures" / "calls"
TOLERANCE_S = 0.05


@pytest.mark.parametrize("name", sorted(p.name for p in CALLS.iterdir()))
def test_scores_match_known_timings(name: str) -> None:
    truth = json.loads((CALLS / name / "truth.json").read_text())
    score = score_call(CALLS / name, Thresholds(), SileroVad())

    latency = score.metric("response_latency_p95_s")
    assert latency is not None
    measured = latency.samples
    assert len(measured) == len(truth["response_latencies_s"]), measured
    for got, want in zip(measured, truth["response_latencies_s"], strict=True):
        assert abs(got - want) <= TOLERANCE_S, f"latency {got} vs {want}"

    yields = score.metric("time_to_yield_p95_s")
    assert yields is not None
    assert len(yields.samples) == len(truth["time_to_yield_s"]), yields.samples
    for got, want in zip(yields.samples, truth["time_to_yield_s"], strict=True):
        assert abs(got - want) <= TOLERANCE_S, f"yield {got} vs {want}"

    talk = score.metric("talk_over_ratio")
    assert talk is not None and talk.value is not None
    assert abs(talk.value - truth["talk_over_ratio"]) <= 0.03, f"talk-over {talk.value}"


def test_failures_become_located_findings() -> None:
    score = score_call(CALLS / "barge_in_ignored", Thresholds(), SileroVad())
    yield_metric = score.metric("time_to_yield_p95_s")
    assert yield_metric is not None and yield_metric.passed is False
    [finding] = [f for f in score.findings if f.metric == "time_to_yield"]
    assert "kept talking" in finding.message and finding.end_s is not None

    slow = score_call(CALLS / "turn_taking", Thresholds(), SileroVad())
    assert [round(f.t_s, 1) for f in slow.findings if f.metric == "response_latency"] != []
    assert slow.metric("response_latency_p95_s").passed is False  # type: ignore[union-attr]
