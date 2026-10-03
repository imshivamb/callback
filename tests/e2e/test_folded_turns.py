"""An interruption answered only inside the agent's next reply is "folded", not unanswered."""

from callback_voice.core.models.finding import Finding
from callback_voice.core.models.metric import Metric
from callback_voice.core.models.turn import Turn
from callback_voice.scoring.metrics.folded_turns import fold_unanswered
from callback_voice.scoring.timeline.caller_utterance import CallerUtterance
from callback_voice.scoring.timeline.segment import Segment


def _utt(start: float, end: float, text: str, tag: str) -> CallerUtterance:
    seg = Segment(start, end)
    return CallerUtterance(
        seg, seg, text, tag, chaos_id="barge_in-1" if tag == "barge_in" else None
    )


UTTERANCES = [
    _utt(0.0, 3.0, "Can you help me plan dinner for four people tonight?", "line"),
    _utt(21.0, 23.0, "Sorry, make that for 6 people.", "barge_in"),
    _utt(25.5, 28.0, "What do I need to buy?", "line"),
]
FINDINGS = [
    Finding(metric="unanswered_turns", t_s=23.0, end_s=25.5, message="The caller waited 2.5 s.")
]
METRICS = [Metric(name="unanswered_turns", value=1, unit="count", threshold=0, passed=False)]


def _reply(text: str) -> list[Turn]:
    return [Turn(speaker="agent", start_s=31.0, end_s=36.0, text=text)]


def _late_acknowledgement() -> Turn:
    """A short cut-off "No problem" that starts while the caller's next line is playing."""
    return Turn(speaker="agent", start_s=25.8, end_s=26.2, text="No problem we-")


def test_interruption_worked_into_the_next_reply_is_folded() -> None:
    metrics, findings = fold_unanswered(
        METRICS, FINDINGS, UTTERANCES, _reply("For six people you need pasta."), 0
    )
    by_name = {m.name: m for m in metrics}
    assert by_name["unanswered_turns"].value == 0
    assert by_name["unanswered_turns"].passed is True
    assert by_name["folded_turns"].value == 1
    assert [(f.metric, f.severity) for f in findings] == [("folded_turns", "warn")]


def test_interruption_the_reply_never_mentions_stays_unanswered() -> None:
    metrics, findings = fold_unanswered(
        METRICS, FINDINGS, UTTERANCES, _reply("You need pasta and pesto."), 0
    )
    assert metrics == METRICS
    assert findings == FINDINGS


def test_only_barge_ins_can_be_folded() -> None:
    plain = [*UTTERANCES[:1], _utt(21.0, 23.0, "Make that for 6 people.", "line"), UTTERANCES[2]]
    metrics, _ = fold_unanswered(METRICS, FINDINGS, plain, _reply("For six people, pasta."), 0)
    assert metrics == METRICS


def test_a_late_fragment_over_the_next_line_is_not_the_reply() -> None:
    transcript = [_late_acknowledgement(), *_reply("For six people you need pasta.")]
    metrics, findings = fold_unanswered(METRICS, FINDINGS, UTTERANCES, transcript, 0)
    assert {m.name: m.value for m in metrics}["folded_turns"] == 1
    assert [f.metric for f in findings] == ["folded_turns"]


def test_a_late_fragment_and_a_full_reply_that_ignore_it_stay_unanswered() -> None:
    transcript = [_late_acknowledgement(), *_reply("You need pasta and pesto.")]
    metrics, findings = fold_unanswered(METRICS, FINDINGS, UTTERANCES, transcript, 0)
    assert metrics == METRICS
    assert findings == FINDINGS
