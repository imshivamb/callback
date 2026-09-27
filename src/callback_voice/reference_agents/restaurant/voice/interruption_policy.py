from typing import Literal

from callback_voice.reference_agents.restaurant.voice.behavior import AgentBehavior

type Decision = Literal["wait", "judge", "yield", "deaf"]

_JUDGE_AFTER_S = 0.25
_UNJUDGED_YIELD_AFTER_S = 0.9
_JUDGED_BACKCHANNEL_LIMIT_S = 1.5


def interruption_decision(
    behavior: AgentBehavior, *, speech_s: float, sentence_index: int, judged_backchannel: bool
) -> Decision:
    """What the agent does when the caller talks while it is speaking.

    The good policy waits ~0.25 s, transcribes the partial speech with a fast model
    and yields unless it is a backchannel. If the judgement is slow, it yields at
    0.9 s anyway. Speech already judged a backchannel is talked through unless it
    keeps going past 1.5 s (``speech_s`` includes the detector's end hangover, so a
    long "mm-hmm" can read close to 1 s).

    The buggy policy ignores everything during its first sentence, then yields to
    any sound. The ``ignore`` policy never yields.
    """
    if behavior.barge_in == "ignore":
        return "deaf"
    if behavior.barge_in == "deaf_first_sentence" and sentence_index <= 0:
        return "deaf"
    if not behavior.filter_backchannels:
        return "yield"
    if judged_backchannel:
        return "yield" if speech_s >= _JUDGED_BACKCHANNEL_LIMIT_S else "wait"
    if speech_s >= _UNJUDGED_YIELD_AFTER_S:
        return "yield"
    return "wait" if speech_s < _JUDGE_AFTER_S else "judge"
