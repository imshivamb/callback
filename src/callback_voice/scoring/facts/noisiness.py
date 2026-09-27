import numpy as np

from callback_voice.audio.format import SAMPLE_RATE, Audio

_FRAME = 320  # 20 ms


def noisiness(audio: Audio, start_s: float, end_s: float) -> float | None:
    """Mean spectral flatness of ``audio`` between two times: near 0 for voiced speech,
    near 1 for noise. None if the span is too short to measure.
    """
    segment = audio[max(0, round(start_s * SAMPLE_RATE)) : round(end_s * SAMPLE_RATE)]
    count = segment.size // _FRAME
    if count == 0:
        return None
    frames = segment[: count * _FRAME].reshape(count, _FRAME).astype(np.float64)
    spectrum = np.abs(np.fft.rfft(frames * np.hanning(_FRAME), axis=1)) + 1e-9
    flatness = np.exp(np.mean(np.log(spectrum), axis=1)) / np.mean(spectrum, axis=1)
    return float(flatness.mean())
