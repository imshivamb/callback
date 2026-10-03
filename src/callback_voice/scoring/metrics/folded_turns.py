import re

from callback_voice.core.models.finding import Finding
from callback_voice.core.models.metric import Metric
from callback_voice.core.models.turn import Turn
from callback_voice.scoring.timeline.caller_utterance import CallerUtterance

_STOP_TEXT = (
    "a an and are as at be but by can could do does for from had has have he her his i if in "
    "is it its just let make me my no not of oh ok okay on one or our please so sorry sure "
    "that the their then there these they this to us was we were will with would yes you your"
)
_NUMBER_TEXT = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen twenty"
)
_STOPWORDS = frozenset(_STOP_TEXT.split())
_NUMBERS = {str(i): w for i, w in enumerate(_NUMBER_TEXT.split())}


def fold_unanswered(
    metrics: list[Metric],
    findings: list[Finding],
    utterances: list[CallerUtterance],
    transcript: list[Turn],
    max_unanswered: int,
) -> tuple[list[Metric], list[Finding]]:
    """Count an interruption the agent worked into its next answer as handled, but flag it.

    An unanswered turn after a barge-in is *folded* when the agent's next full reply,
    the first one that starts after the caller's following line has ended, repeats a
    content word that the interruption introduced (a word no earlier caller line used;
    digits and number words are the same word). A short, late acknowledgement that
    overlaps the caller's following line is not that reply.
    A folded turn no longer counts in ``unanswered_turns``; it is reported in
    ``folded_turns`` and as a warning. Every other unanswered turn is left as it was.
    """
    folded: list[Finding] = []
    kept: list[Finding] = []
    for finding in findings:
        utt = _interruption(finding, utterances)
        if utt is not None and _is_folded(finding, utt, utterances, transcript):
            folded.append(
                Finding(
                    metric="folded_turns",
                    t_s=finding.t_s,
                    end_s=finding.end_s,
                    message=(
                        f"The agent did not answer “{_short(utt.text)}” on its own but worked "
                        "it into its next answer."
                    ),
                    severity="warn",
                    chaos_id=utt.chaos_id,
                )
            )
        else:
            kept.append(finding)
    if not folded:
        return metrics, findings
    updated: list[Metric] = []
    for metric in metrics:
        if metric.name == "unanswered_turns" and metric.value is not None:
            value = metric.value - len(folded)
            metric = metric.model_copy(update={"value": value, "passed": value <= max_unanswered})
        updated.append(metric)
    updated.append(
        Metric(
            name="folded_turns",
            value=len(folded),
            unit="count",
            detail="interruptions answered only inside the agent's next reply; counted as handled",
        )
    )
    return updated, sorted([*kept, *folded], key=lambda f: f.t_s)


def _interruption(finding: Finding, utterances: list[CallerUtterance]) -> CallerUtterance | None:
    if finding.metric != "unanswered_turns":
        return None
    return next(
        (u for u in utterances if u.tag == "barge_in" and abs(u.speech.end_s - finding.t_s) < 1e-6),
        None,
    )


def _is_folded(
    finding: Finding,
    utt: CallerUtterance,
    utterances: list[CallerUtterance],
    transcript: list[Turn],
) -> bool:
    earlier = {
        w for u in utterances if u.speech.start_s < utt.speech.start_s for w in _words(u.text)
    }
    introduced = _words(utt.text) - earlier
    if not introduced or finding.end_s is None:
        return False
    following = next((u for u in utterances if abs(u.speech.start_s - finding.end_s) < 1e-6), None)
    after_s = following.speech.end_s if following is not None else finding.end_s
    reply = next((t for t in transcript if t.speaker == "agent" and t.start_s >= after_s), None)
    return reply is not None and bool(introduced & _words(reply.text))


def _words(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9']+", text.lower())
    return {_NUMBERS.get(t, t) for t in tokens} - _STOPWORDS


def _short(text: str, limit: int = 48) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
