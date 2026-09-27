from callback_voice.scoring.timeline.call_timeline import CallTimeline
from callback_voice.scoring.timeline.segment import Segment

_MERGE_GAP_S = 1.0


def agent_turn_spans(timeline: CallTimeline) -> list[Segment]:
    """Group the agent's speech segments into turns.

    Segments merge across pauses shorter than 1 s, unless the caller started a
    real line (not a backchannel) in between, which ends the agent's turn.
    """
    caller_starts = [u.speech.start_s for u in timeline.utterances if u.takes_floor]
    turns: list[Segment] = []
    for seg in timeline.agent_speech:
        if turns:
            last = turns[-1]
            caller_between = any(last.end_s <= t < seg.start_s for t in caller_starts)
            if seg.start_s - last.end_s < _MERGE_GAP_S and not caller_between:
                turns[-1] = Segment(last.start_s, seg.end_s)
                continue
        turns.append(seg)
    return turns
