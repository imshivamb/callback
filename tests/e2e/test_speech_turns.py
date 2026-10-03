"""The speech view shows each side's own words, once, where they were said."""

from callback_voice.core.models.turn import Turn, TurnWord
from callback_voice.scoring.timeline.call_timeline import CallTimeline
from callback_voice.scoring.timeline.caller_utterance import CallerUtterance
from callback_voice.scoring.timeline.segment import Segment
from callback_voice.scoring.timeline.speech_turns import speech_turns


def _word(text: str, start: float, end: float) -> TurnWord:
    return TurnWord(text=text, start_s=start, end_s=end, p=0.9)


def test_agent_pieces_carry_only_the_agent_words_said_inside_them() -> None:
    caller_seg, first, second = Segment(2.0, 4.0), Segment(0.0, 1.5), Segment(5.0, 7.0)
    timeline = CallTimeline(
        duration_s=8.0,
        agent_speech=[first, second],
        caller_speech=[caller_seg],
        utterances=[CallerUtterance(caller_seg, caller_seg, "Make it six.", "barge_in")],
    )
    transcript = [
        Turn(
            speaker="agent",
            start_s=0.0,
            end_s=7.0,
            text="How about pasta then for six",
            words=[
                _word("How", 0.1, 0.4),
                _word("about", 0.5, 0.9),
                _word("pasta", 1.0, 1.4),
                _word("then", 5.1, 5.4),
                _word("for", 5.5, 5.8),
                _word("six", 5.9, 6.4),
            ],
        ),
        Turn(speaker="caller", start_s=2.0, end_s=4.0, text="Make it six."),
    ]
    texts = {(t.speaker, t.start_s): t.text for t in speech_turns(timeline, transcript)}
    assert texts[("agent", 0.0)] == "How about pasta"
    assert texts[("agent", 5.0)] == "then for six"
    assert texts[("caller", 2.0)] == "Make it six."
