from callback_voice.audio.format import Audio
from callback_voice.core.models.call_event import CallEvent
from callback_voice.providers.vad.base import VoiceActivityModel
from callback_voice.scoring.timeline.call_timeline import CallTimeline
from callback_voice.scoring.timeline.caller_utterance import CallerUtterance
from callback_voice.scoring.timeline.interval_ops import overlapping
from callback_voice.scoring.timeline.segment import Segment
from callback_voice.scoring.timeline.speech_segments import speech_segments

_MATCH_MARGIN_S = 0.1


def build_timeline(
    *,
    agent: Audio,
    caller_clean: Audio,
    events: list[CallEvent],
    vad: VoiceActivityModel,
    duration_s: float,
) -> CallTimeline:
    """Run VAD on both sides and attach each caller utterance to its measured speech.

    The agent side is measured from what the caller heard. The caller side is
    measured from the clean stem, so a noise bed cannot move the caller's edges.
    """
    agent_speech = speech_segments(agent, vad)
    caller_speech = speech_segments(caller_clean, vad)
    utterances = []
    for event in events:
        if event.kind != "caller_utterance" or event.end_s is None:
            continue
        planned = Segment(event.t_s, event.end_s)
        window = Segment(planned.start_s - _MATCH_MARGIN_S, planned.end_s + _MATCH_MARGIN_S)
        matched = [s for s in overlapping(caller_speech, window)]
        speech = (
            Segment(max(matched[0].start_s, window.start_s), min(matched[-1].end_s, window.end_s))
            if matched
            else planned
        )
        utterances.append(
            CallerUtterance(
                speech=speech,
                planned=planned,
                text=event.text or "",
                tag=str(event.data.get("tag", "line")),
                chaos_id=event.chaos_id,
                chaos_type=event.chaos_type,
            )
        )
    return CallTimeline(duration_s, agent_speech, caller_speech, utterances, events)
