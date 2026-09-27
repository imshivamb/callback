import numpy as np

from callback_voice.audio.format import SAMPLE_RATE, Audio

_INITIAL_S = 60


class AudioTape:
    """An append-only mono buffer that grows geometrically and slices by time."""

    def __init__(self) -> None:
        self._data = np.zeros(_INITIAL_S * SAMPLE_RATE, dtype=np.float32)
        self._size = 0

    @property
    def duration_s(self) -> float:
        return self._size / SAMPLE_RATE

    def append(self, audio: Audio) -> None:
        self.write_at(self._size, audio)

    def write_at(self, sample: int, audio: Audio, *, mix: bool = False) -> None:
        """Write (or mix) ``audio`` starting at ``sample``, growing and zero-filling as needed."""
        end = sample + audio.size
        if end > self._data.size:
            grown = np.zeros(max(end, self._data.size * 2), dtype=np.float32)
            grown[: self._size] = self._data[: self._size]
            self._data = grown
        if mix:
            self._data[sample:end] += audio
        else:
            self._data[sample:end] = audio
        self._size = max(self._size, end)

    def slice(self, start_s: float, end_s: float) -> Audio:
        start = max(0, round(start_s * SAMPLE_RATE))
        end = min(self._size, round(end_s * SAMPLE_RATE))
        return self._data[start:end].copy() if end > start else np.zeros(0, np.float32)

    def to_array(self) -> Audio:
        return self._data[: self._size].copy()
