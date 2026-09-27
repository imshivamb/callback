"""Real calls: scripted caller -> WebSocket -> reference agent, with real speech models."""

from importlib.util import find_spec
from pathlib import Path

import pytest
import soundfile as sf

from callback_voice.reference_agents.restaurant.voice.behavior import BUGGY, GOOD
from tests.e2e.reference_call import MOVE_SCRIPT, call_reference_agent

pytestmark = pytest.mark.skipif(
    find_spec("kokoro_onnx") is None or find_spec("faster_whisper") is None,
    reason='needs pip install "callback-voice[local]"',
)


def caller_lines(call) -> list[str]:
    return [e.text for e in call.outcome.log.events if e.kind == "caller_utterance"]


async def test_good_agent_completes_the_booking_move(tmp_path: Path) -> None:
    call = await call_reference_agent(GOOD, tmp_path, "e2e-good")

    assert call.outcome.end_reason == "caller_hangup"
    assert caller_lines(call) == list(MOVE_SCRIPT)
    expected = {"status": "moved", "day": "saturday", "hour": 19, "minute": 30}
    assert call.end_state.items() >= expected.items(), call.end_state
    assert call.outcome.max_lateness_s < 0.1

    audio, rate = sf.read(tmp_path / "call.wav")
    assert rate == 16_000 and audio.shape[1] == 2
    assert audio[:, 0].std() > 0.01 and audio[:, 1].std() > 0.01
    assert (tmp_path / "caller_clean.wav").exists() and (tmp_path / "events.jsonl").exists()


async def test_buggy_agent_is_measurably_slower(tmp_path: Path) -> None:
    good = await call_reference_agent(GOOD, tmp_path / "good", "e2e-good-2")
    buggy = await call_reference_agent(BUGGY, tmp_path / "buggy", "e2e-buggy")

    def mean_gap(call) -> float:
        events = call.outcome.log.events
        ends = [e.end_s for e in events if e.kind == "caller_utterance"]
        starts = [e.t_s for e in events if e.kind == "agent_turn_start"]
        gaps = [min((s for s in starts if s > end), default=end) - end for end in ends[:-1] if end]
        return sum(gaps) / len(gaps)

    assert mean_gap(buggy) > mean_gap(good) + 0.8
