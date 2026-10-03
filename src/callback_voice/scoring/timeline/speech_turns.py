from callback_voice.core.models.turn import Turn
from callback_voice.scoring.timeline.call_timeline import CallTimeline
from callback_voice.scoring.timeline.segment import Segment


def speech_turns(timeline: CallTimeline, transcript: list[Turn]) -> list[Turn]:
    """Every measured stretch of speech on both channels, in time order.

    Caller stretches carry the line the caller said there; agent stretches carry the
    transcribed words that overlap them, when the call was transcribed.
    """
    turns = [
        Turn(
            speaker="caller",
            start_s=round(seg.start_s, 3),
            end_s=round(seg.end_s, 3),
            text=next((u.text for u in timeline.utterances if u.speech.overlap(seg) > 0), ""),
        )
        for seg in timeline.caller_speech
    ]
    turns += [
        Turn(
            speaker="agent",
            start_s=round(seg.start_s, 3),
            end_s=round(seg.end_s, 3),
            text=_agent_text(seg, transcript),
        )
        for seg in timeline.agent_speech
    ]
    return sorted(turns, key=lambda t: t.start_s)


def _agent_text(seg: Segment, transcript: list[Turn]) -> str:
    """The agent's own words inside ``seg``; never the caller's, and never a whole turn per piece."""
    words: list[str] = []
    for turn in transcript:
        if turn.speaker != "agent" or Segment(turn.start_s, turn.end_s).overlap(seg) <= 0:
            continue
        if not turn.words:
            words.append(turn.text)
            continue
        words += [w.text.strip() for w in turn.words if _midpoint_in(w.start_s, w.end_s, seg)]
    return " ".join(w for w in words if w)


def _midpoint_in(start_s: float, end_s: float, seg: Segment) -> bool:
    return seg.contains((start_s + end_s) / 2)
