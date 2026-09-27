"""Scoring accuracy: synthetic calls with known timings must score within ±50 ms."""

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

    unanswered = score.metric("unanswered_turns")
    assert unanswered is not None
    assert unanswered.value == len(truth.get("unanswered_turns", [])), unanswered


def test_failures_become_located_findings() -> None:
    score = score_call(CALLS / "barge_in_ignored", Thresholds(), SileroVad())
    yield_metric = score.metric("time_to_yield_p95_s")
    assert yield_metric is not None and yield_metric.passed is False
    [finding] = [f for f in score.findings if f.metric == "time_to_yield"]
    assert "kept talking" in finding.message and finding.end_s is not None

    slow = score_call(CALLS / "turn_taking", Thresholds(), SileroVad())
    assert [round(f.t_s, 1) for f in slow.findings if f.metric == "response_latency"] != []
    assert slow.metric("response_latency_p95_s").passed is False  # type: ignore[union-attr]


def test_unanswered_turn_fails_only_when_the_caller_waited() -> None:
    truth = json.loads((CALLS / "unanswered" / "truth.json").read_text())
    [want] = truth["unanswered_turns"]
    score = score_call(CALLS / "unanswered", Thresholds(), SileroVad())

    metric = score.metric("unanswered_turns")
    assert metric is not None and metric.method == "deterministic"
    assert metric.value == 1 and metric.threshold == 0 and metric.passed is False
    [finding] = [f for f in score.findings if f.metric == "unanswered_turns"]
    assert finding.severity == "fail" and abs(finding.t_s - want["t_s"]) <= TOLERANCE_S
    assert want["text"] in finding.message and "waited 3.0 s" in finding.message, finding.message
    # The back-to-back pair left the agent no opening: neither a finding nor a warning.
    assert not [f for f in score.findings if "never answered" in f.message and f is not finding]

    lenient = score_call(CALLS / "unanswered", Thresholds(unanswered_turns=1), SileroVad())
    assert lenient.metric("unanswered_turns").passed is True  # type: ignore[union-attr]
