from callback_voice.reference_agents.restaurant.voice.behavior import BUGGY, GOOD
from callback_voice.reference_agents.restaurant.voice.interruption_policy import (
    interruption_decision,
)
from callback_voice.reference_agents.restaurant.voice.is_backchannel import is_backchannel


def test_good_agent_judges_then_yields_to_long_speech() -> None:
    kw = {"sentence_index": 0, "judged_backchannel": False}
    assert interruption_decision(GOOD, speech_s=0.1, **kw) == "wait"
    assert interruption_decision(GOOD, speech_s=0.3, **kw) == "judge"
    assert interruption_decision(GOOD, speech_s=1.0, **kw) == "yield"
    assert (
        interruption_decision(GOOD, speech_s=0.5, sentence_index=0, judged_backchannel=True)
        == "wait"
    )


def test_buggy_agent_is_deaf_then_trigger_happy() -> None:
    assert (
        interruption_decision(BUGGY, speech_s=1.0, sentence_index=0, judged_backchannel=False)
        == "deaf"
    )
    assert (
        interruption_decision(BUGGY, speech_s=0.1, sentence_index=1, judged_backchannel=False)
        == "yield"
    )


def test_backchannel_words() -> None:
    assert all(is_backchannel(t) for t in ["Mm-hmm.", "okay", "Haan haan", "", "Right."])
    assert not any(is_backchannel(t) for t in ["haan haan, Saturday", "wait, stop", "Sorry?"])
