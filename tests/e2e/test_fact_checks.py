"""Required facts on real speech: a wrong value fails, a transcription loss goes to review."""

import json
from importlib.util import find_spec
from pathlib import Path

import pytest

from callback_voice.core.models.expectation import Expectation
from callback_voice.providers.stt.faster_whisper_stt import FasterWhisperStt
from callback_voice.providers.vad.silero_vad import SileroVad
from callback_voice.scoring.evaluate_call import evaluate_call

FIXTURES = Path(__file__).parents[1] / "fixtures" / "facts"
FACTS = Expectation.model_validate(
    {
        "entities_spoken": [
            "DX7Q2",
            {"count": 4, "label": "count 4 people"},
            {"time": "7:30 PM"},
            {"phone": "98100 12345"},
        ]
    }
)

pytestmark = pytest.mark.skipif(
    find_spec("faster_whisper") is None, reason='needs "callback-voice[local]"'
)


async def evaluate(name: str):
    return await evaluate_call(
        FIXTURES / name,
        FACTS,
        vad=SileroVad(),
        stt=FasterWhisperStt("small", words=True),
        careful_stt=FasterWhisperStt("small", words=True, beam_size=5),
        judge=None,
        state=None,
        language="en",
    )


def metric(result, name: str) -> dict:
    return next(m for m in result.metrics if m.name == name).model_dump()


async def test_transcription_loss_is_sent_to_review_not_blamed_on_the_agent() -> None:
    result = await evaluate("masked-code")

    [item] = result.review
    assert item.check == "code DX7Q2" and "noise" in item.reason, item
    fidelity = metric(result, "entity_fidelity")
    assert fidelity["passed"] is True, fidelity  # the three settled facts are correct
    assert metric(result, "facts_uncertain")["value"] == 1
    assert not [
        f for f in result.findings if f.metric == "entity_fidelity" and f.severity == "fail"
    ]


async def test_a_different_value_spoken_is_still_a_failure() -> None:
    result = await evaluate("garbled-code")

    assert result.review == []
    fidelity = metric(result, "entity_fidelity")
    assert fidelity["passed"] is False and fidelity["value"] == 0.75, fidelity
    [finding] = [f for f in result.findings if f.metric == "entity_fidelity"]
    assert "B X 7 Q 2" in finding.message and "D X 7 Q 2" in finding.message


@pytest.mark.parametrize("name", ["masked-code", "garbled-code"])
async def test_party_size_time_and_phone_are_checked(name: str) -> None:
    truth = json.loads((FIXTURES / name / "truth.json").read_text())
    result = await evaluate(name)
    bad = [f.message for f in result.findings if f.metric == "entity_fidelity"]
    for check in ("count 4 people", "time 7:30 PM", "phone 98100 12345"):
        assert truth[check] == "correct"
        assert not any(check in message for message in bad), bad
