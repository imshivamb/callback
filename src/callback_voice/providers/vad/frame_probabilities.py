import numpy as np
from numpy.typing import NDArray

from callback_voice.audio.format import Audio
from callback_voice.providers.vad.base import VoiceActivityModel


def frame_probabilities(model: VoiceActivityModel, audio: Audio) -> NDArray[np.float32]:
    """Speech probability for every consecutive window of a whole recording channel.

    Window ``i`` covers samples ``[i * w, (i + 1) * w)``; a short tail is zero-padded.
    """
    model.reset()
    width = model.window_samples
    count = -(-audio.size // width)
    padded = np.zeros(count * width, dtype=np.float32)
    padded[: audio.size] = audio
    windows = padded.reshape(count, width)
    return np.fromiter((model.probability(w) for w in windows), dtype=np.float32, count=count)
