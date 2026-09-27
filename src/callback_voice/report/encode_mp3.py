import base64
import io

import numpy as np
import soundfile as sf


def encode_mp3(samples: np.ndarray, sample_rate: int) -> str:
    """A ``data:`` URI of the audio as MP3, so the report plays it with no files beside it.

    About 36 kbit/s for 16 kHz stereo speech: a one-minute call is roughly 270 KB.
    """
    buffer = io.BytesIO()
    sf.write(buffer, samples, sample_rate, format="MP3", compression_level=0.5)
    return "data:audio/mpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
