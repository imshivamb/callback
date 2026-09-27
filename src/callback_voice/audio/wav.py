"""Reading and writing audio files in the internal format."""

from pathlib import Path

import numpy as np
import soundfile as sf

from callback_voice.audio.format import SAMPLE_RATE, Audio
from callback_voice.audio.resample import resample


def read_mono(path: Path, sample_rate: int = SAMPLE_RATE) -> Audio:
    """Read any soundfile-supported file as mono float32 at ``sample_rate``."""
    data, file_rate = sf.read(str(path), dtype="float32", always_2d=True)
    mono = data.mean(axis=1).astype(np.float32)
    return resample(mono, int(file_rate), sample_rate)


def write_wav(path: Path, audio: Audio, sample_rate: int = SAMPLE_RATE) -> None:
    """Write mono ``(n,)`` or multichannel ``(n, channels)`` float audio as PCM16 WAV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), audio, sample_rate, subtype="PCM_16")
