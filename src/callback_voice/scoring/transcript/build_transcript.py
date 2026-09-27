from callback_voice.audio.format import SAMPLE_RATE, Audio
from callback_voice.core.models.turn import Turn, TurnWord
from callback_voice.providers.stt.base import SpeechToText
from callback_voice.scoring.timeline.call_timeline import CallTimeline
from callback_voice.scoring.transcript.agent_turn_spans import agent_turn_spans

_PAD_S = 0.1


async def build_transcript(
    timeline: CallTimeline, agent_audio: Audio, stt: SpeechToText, language: str | None
) -> list[Turn]:
    """Both sides of the call as turns, in time order.

    Agent words come from transcribing the agent channel offline (what the caller
    actually heard). Caller words are known: they come from the event log. A turn
    records any barge-in that overlapped it.
    """
    turns: list[Turn] = []
    for span in agent_turn_spans(timeline):
        start = max(0, round((span.start_s - _PAD_S) * SAMPLE_RATE))
        end = round((span.end_s + _PAD_S) * SAMPLE_RATE)
        heard = await stt.transcribe(agent_audio[start:end], language=language)
        offset = start / SAMPLE_RATE
        words = [
            TurnWord(
                text=w.text,
                start_s=round(offset + w.start_s, 3),
                end_s=round(offset + w.end_s, 3),
                p=round(w.probability, 3),
            )
            for w in heard.words
        ]
        text = heard.text.strip()
        cut_in = next(
            (
                u
                for u in timeline.utterances
                if u.tag == "barge_in" and span.start_s < u.speech.start_s < span.end_s
            ),
            None,
        )
        turns.append(
            Turn(
                speaker="agent",
                start_s=round(span.start_s, 3),
                end_s=round(span.end_s, 3),
                text=text,
                interrupted_by=cut_in.chaos_id if cut_in else None,
                words=words,
            )
        )
    for utt in timeline.utterances:
        turns.append(
            Turn(
                speaker="caller",
                start_s=round(utt.speech.start_s, 3),
                end_s=round(utt.speech.end_s, 3),
                text=utt.text,
                chaos_ids=[utt.chaos_id] if utt.chaos_id else [],
            )
        )
    return sorted(turns, key=lambda t: t.start_s)
