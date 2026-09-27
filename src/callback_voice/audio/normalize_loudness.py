import numpy as np

from callback_voice.audio.format import SAMPLE_RATE, Audio

TARGET_SPEECH_DBFS = -20.0
_WINDOW = SAMPLE_RATE // 50
_ACTIVE_DB_BELOW_PEAK = 30.0


def normalize_loudness(audio: Audio, target_dbfs: float = TARGET_SPEECH_DBFS) -> Audio:
    """Scale speech so its active (non-silent) RMS sits at ``target_dbfs``.

    A fixed speech level is what makes a scenario's ``snr_db`` mean the same thing
    for every voice and TTS engine.
    """
    count = audio.size // _WINDOW
    if count == 0:
        return audio
    frames = audio[: count * _WINDOW].reshape(count, _WINDOW).astype(np.float64)
    power = np.mean(frames**2, axis=1)
    active = power[power >= power.max() * 10 ** (-_ACTIVE_DB_BELOW_PEAK / 10)]
    level = float(np.sqrt(active.mean())) if active.size else 0.0
    if level <= 1e-6:
        return audio
    gain = 10 ** (target_dbfs / 20) / level
    clipped: Audio = np.clip(audio * gain, -1.0, 1.0).astype(np.float32)
    return clipped
