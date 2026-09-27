"""The judge-vs-facts fixture: re-scoring the real call must still find the wrong code."""

import json
from importlib.util import find_spec
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from callback_voice.core.models.expectation import Expectation
from callback_voice.providers.stt.faster_whisper_stt import FasterWhisperStt
from callback_voice.providers.vad.silero_vad import SileroVad
from callback_voice.scoring.evaluate_call import evaluate_call

FIXTURE = Path(__file__).parents[1] / "fixtures" / "disagreements" / "judge-vs-facts-wrong-code"
pytestmark = pytest.mark.skipif(
    find_spec("faster_whisper") is None, reason='needs "callback-voice[local]"'
)


async def test_hard_check_still_calls_the_code_wrong(tmp_path: Path) -> None:
    audio, rate = sf.read(FIXTURE / "call.mp3", dtype="float32")
    sf.write(tmp_path / "call.wav", audio, rate, subtype="PCM_16")
    sf.write(
        tmp_path / "caller_clean.wav", np.ascontiguousarray(audio[:, 0]), rate, subtype="PCM_16"
    )
    (tmp_path / "events.jsonl").write_bytes((FIXTURE / "events.jsonl").read_bytes())
    expected = json.loads((FIXTURE / "expected.json").read_text())
    recorded = json.loads((FIXTURE / "recorded.json").read_text())

    result = await evaluate_call(
        tmp_path,
        Expectation.model_validate({"entities_spoken": ["DX7Q2"]}),
        vad=SileroVad(),
        stt=FasterWhisperStt("small", words=True),
        careful_stt=FasterWhisperStt("small", words=True, beam_size=5),
        judge=None,
        state=None,
        language="en",
    )

    assert result.review == [], result.review  # confident, voiced: not a transcription doubt
    [finding] = [f for f in result.findings if f.metric == "entity_fidelity"]
    assert expected["heard"] in finding.message
    lo, hi = expected["readback_turn_s"]
    assert lo - 1 <= finding.t_s <= hi
    # The judge's recorded view of the same call did not fail it.
    assert all(m["passed"] is None for m in recorded["judge_metrics"])
    assert min(m["value"] for m in recorded["judge_metrics"]) >= 4
