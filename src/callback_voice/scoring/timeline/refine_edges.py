import numpy as np
from numpy.typing import NDArray

from callback_voice.audio.format import SAMPLE_RATE, Audio
from callback_voice.scoring.timeline.segment import Segment

_WINDOW_S = 0.01
_SEARCH_S = 0.2
_ABSOLUTE_FLOOR_DB = -40.0
_ABOVE_NOISE_DB = 10.0


def refine_edges(segments: list[Segment], audio: Audio) -> list[Segment]:
    """Snap VAD segment edges to where speech energy actually starts and stops.

    Silero decides *whether* there is speech in 32 ms windows and confirms edges
    late; this moves each edge (within ±200 ms, never into a neighbouring segment)
    to the first/last 10 ms window above a noise-adaptive threshold. It is what
    brings timing error inside the ±50 ms budget.
    """
    if not segments:
        return segments
    width = round(_WINDOW_S * SAMPLE_RATE)
    count = audio.size // width
    levels: NDArray[np.float64] = 10 * np.log10(
        np.mean(audio[: count * width].reshape(count, width).astype(np.float64) ** 2, axis=1)
        + 1e-12
    )
    threshold = max(_ABSOLUTE_FLOOR_DB, float(np.percentile(levels, 20)) + _ABOVE_NOISE_DB)
    loud = levels > threshold
    refined: list[Segment] = []
    for i, seg in enumerate(segments):
        lower = segments[i - 1].end_s if i > 0 else 0.0
        upper = segments[i + 1].start_s if i + 1 < len(segments) else count * _WINDOW_S
        start = _first_loud(
            loud, max(lower, seg.start_s - _SEARCH_S), min(seg.end_s, seg.start_s + _SEARCH_S)
        )
        end = _last_loud(
            loud, max(seg.start_s, seg.end_s - _SEARCH_S), min(upper, seg.end_s + _SEARCH_S)
        )
        new_start = seg.start_s if start is None else start
        new_end = seg.end_s if end is None else end
        refined.append(Segment(new_start, new_end) if new_end > new_start else seg)
    return refined


def _first_loud(loud: NDArray[np.bool_], from_s: float, to_s: float) -> float | None:
    lo, hi = int(from_s / _WINDOW_S), min(loud.size, int(np.ceil(to_s / _WINDOW_S)))
    hits = np.flatnonzero(loud[lo:hi])
    return None if hits.size == 0 else (lo + hits[0]) * _WINDOW_S


def _last_loud(loud: NDArray[np.bool_], from_s: float, to_s: float) -> float | None:
    lo, hi = int(from_s / _WINDOW_S), min(loud.size, int(np.ceil(to_s / _WINDOW_S)))
    hits = np.flatnonzero(loud[lo:hi])
    return None if hits.size == 0 else (lo + hits[-1] + 1) * _WINDOW_S
