import numpy as np

from callback_voice.audio.format import SAMPLE_RATE, Audio

_WINDOW = SAMPLE_RATE // 100  # 10 ms


def trim_silence(audio: Audio, threshold_dbfs: float = -45.0, keep_s: float = 0.03) -> Audio:
    """Strip leading and trailing near-silence, keeping ``keep_s`` of margin.

    TTS engines pad clips with silence; left in, it would shift every chaos timing
    and make a backchannel look longer than it sounds.
    """
    if audio.size < _WINDOW:
        return audio
    count = audio.size // _WINDOW
    frames = audio[: count * _WINDOW].reshape(count, _WINDOW)
    levels = 10 * np.log10(np.mean(np.square(frames, dtype=np.float64), axis=1) + 1e-12)
    loud = np.flatnonzero(levels > threshold_dbfs)
    if loud.size == 0:
        return audio[:0]
    keep = round(keep_s * SAMPLE_RATE)
    start = max(0, loud[0] * _WINDOW - keep)
    end = min(audio.size, (loud[-1] + 1) * _WINDOW + keep)
    return audio[start:end]
