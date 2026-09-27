"""Real calls: scripted caller -> WebSocket -> reference agent, scored from the recording."""

from importlib.util import find_spec
from pathlib import Path

import pytest
import soundfile as sf

from callback_voice.core.models.thresholds import Thresholds
from callback_voice.providers.vad.silero_vad import SileroVad
from callback_voice.reference_agents.restaurant.voice.behavior import BUGGY, GOOD
from callback_voice.scoring.score_call import score_call
from tests.e2e.reference_call import MOVE_SCRIPT, call_reference_agent

pytestmark = pytest.mark.skipif(
    find_spec("kokoro_onnx") is None or find_spec("faster_whisper") is None,
    reason='needs pip install "callback-voice[local]"',
)


def caller_lines(call) -> list[str]:
    return [e.text for e in call.outcome.log.events if e.kind == "caller_utterance"]


async def test_good_agent_completes_the_booking_and_passes_latency(tmp_path: Path) -> None:
    call = await call_reference_agent(GOOD, tmp_path, "e2e-good")

    assert call.outcome.end_reason == "caller_hangup"
    assert caller_lines(call) == list(MOVE_SCRIPT)
    expected = {"status": "moved", "day": "saturday", "hour": 19, "minute": 30}
    assert call.end_state.items() >= expected.items(), call.end_state
    assert call.outcome.max_lateness_s < 0.1

    audio, rate = sf.read(tmp_path / "call.wav")
    assert rate == 16_000 and audio.shape[1] == 2

    score = score_call(tmp_path, Thresholds(), SileroVad())
    latency = score.metric("response_latency_p95_s")
    assert latency is not None and len(latency.samples) == len(MOVE_SCRIPT)
    assert latency.passed, latency.samples
    talk = score.metric("talk_over_ratio")
    assert talk is not None and talk.passed, talk.value


async def test_buggy_agent_fails_response_latency(tmp_path: Path) -> None:
    call = await call_reference_agent(BUGGY, tmp_path, "e2e-buggy")
    assert call.outcome.end_reason == "caller_hangup"
    score = score_call(tmp_path, Thresholds(), SileroVad())

    latency = score.metric("response_latency_p95_s")
    assert latency is not None and latency.passed is False, latency.samples
    slow = [f for f in score.findings if f.metric == "response_latency"]
    assert slow and all("to respond" in f.message for f in slow)
