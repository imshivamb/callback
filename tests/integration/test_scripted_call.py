from importlib.util import find_spec
from pathlib import Path

import pytest
import soundfile as sf

from callback_voice.reference_agents.restaurant.voice.behavior import GOOD
from tests.integration.scripted_call import MOVE_SCRIPT, call_reference_agent

pytestmark = [
    pytest.mark.integration,
    pytest.mark.models,
    pytest.mark.skipif(find_spec("kokoro_onnx") is None, reason="needs callback-voice[local]"),
]


async def test_scripted_caller_completes_call_and_saves_stereo_wav(tmp_path: Path) -> None:
    outcome, _ = await call_reference_agent(GOOD, tmp_path, "it-1")
    assert outcome.end_reason == "caller_hangup"
    lines = [e for e in outcome.log.events if e.kind == "caller_utterance"]
    assert [e.text for e in lines] == list(MOVE_SCRIPT)
    audio, rate = sf.read(tmp_path / "call.wav")
    assert rate == 16_000 and audio.shape[1] == 2
    assert audio[:, 0].std() > 0.01 and audio[:, 1].std() > 0.01
    assert outcome.max_lateness_s < 0.1
