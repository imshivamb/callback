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
            text=" ".join(
                t.text for t in transcript if Segment(t.start_s, t.end_s).overlap(seg) > 0
            ),
        )
        for seg in timeline.agent_speech
    ]
    return sorted(turns, key=lambda t: t.start_s)
