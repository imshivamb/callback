from callback_voice.audio.format import SAMPLE_RATE, Audio
from callback_voice.providers.vad.base import VoiceActivityModel
from callback_voice.providers.vad.frame_probabilities import frame_probabilities
from callback_voice.providers.vad.hysteresis import HysteresisTracker, VadParams
from callback_voice.scoring.timeline.refine_edges import refine_edges
from callback_voice.scoring.timeline.segment import Segment

SCORING_VAD = VadParams(
    start_threshold=0.5, end_threshold=0.35, min_speech_s=0.09, min_silence_s=0.25
)


def speech_segments(
    audio: Audio, model: VoiceActivityModel, params: VadParams = SCORING_VAD
) -> list[Segment]:
    """Speech stretches in one recorded channel, by the same hysteresis the live caller uses.

    Pauses shorter than ``min_silence_s`` (between words and sentences) do not split
    a segment. Silero finds the segments; edges are then refined on signal energy.
    """
    tracker = HysteresisTracker(model.window_samples / SAMPLE_RATE, params)
    segments: list[Segment] = []
    start: float | None = None
    for probability in frame_probabilities(model, audio):
        edge = tracker.step(float(probability))
        if edge is None:
            continue
        if edge.kind == "start":
            start = edge.t_s
        elif start is not None:
            segments.append(Segment(start, edge.t_s))
            start = None
    closing = tracker.flush()
    if closing is not None and start is not None:
        segments.append(Segment(start, closing.t_s))
    return refine_edges(segments, audio)
