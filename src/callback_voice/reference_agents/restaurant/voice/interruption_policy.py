from typing import Literal

from callback_voice.reference_agents.restaurant.voice.behavior import AgentBehavior

type Decision = Literal["wait", "judge", "yield", "deaf"]

_JUDGE_AFTER_S = 0.28
_ALWAYS_YIELD_AFTER_S = 0.9


def interruption_decision(
    behavior: AgentBehavior, *, speech_s: float, sentence_index: int, judged_backchannel: bool
) -> Decision:
    """What the agent does when the caller talks while it is speaking.

    The good policy waits ~0.3 s, transcribes the partial speech and yields unless it
    is a backchannel; speech longer than 0.9 s is never a backchannel. The buggy
    policy ignores everything during its first sentence, then yields to any sound.
    """
    if behavior.barge_in == "deaf_first_sentence" and sentence_index <= 0:
        return "deaf"
    if not behavior.filter_backchannels:
        return "yield"
    if speech_s >= _ALWAYS_YIELD_AFTER_S:
        return "yield"
    if judged_backchannel or speech_s < _JUDGE_AFTER_S:
        return "wait"
    return "judge"
