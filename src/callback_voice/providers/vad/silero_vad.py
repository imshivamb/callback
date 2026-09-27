from importlib.resources import files

import numpy as np
from numpy.typing import NDArray

from callback_voice.audio.format import SAMPLE_RATE, Audio
from callback_voice.errors import ProviderUnavailableError

_CONTEXT_SAMPLES = 64
_STATE_SHAPE = (2, 1, 128)


class SileroVad:
    """Silero VAD v5 (MIT) on onnxruntime, bundled with Callback; 32 ms windows at 16 kHz."""

    name = "silero-v5"
    window_samples = 512

    def __init__(self) -> None:
        try:
            import onnxruntime as ort
        except ImportError as exc:  # pragma: no cover - core dependency
            raise ProviderUnavailableError("onnxruntime is not installed") from exc
        options = ort.SessionOptions()
        options.inter_op_num_threads = 1
        options.intra_op_num_threads = 1
        model = files("callback_voice.scoring.vad.assets").joinpath("silero_vad.onnx")
        self._session = ort.InferenceSession(
            model.read_bytes(), sess_options=options, providers=["CPUExecutionProvider"]
        )
        self._sr = np.array(SAMPLE_RATE, dtype=np.int64)
        self.reset()

    def reset(self) -> None:
        self._state: NDArray[np.float32] = np.zeros(_STATE_SHAPE, dtype=np.float32)
        self._context: NDArray[np.float32] = np.zeros((1, _CONTEXT_SAMPLES), dtype=np.float32)

    def probability(self, window: Audio) -> float:
        if window.size != self.window_samples:
            raise ValueError(
                f"Silero needs {self.window_samples}-sample windows, got {window.size}"
            )
        x = np.concatenate([self._context, window.reshape(1, -1).astype(np.float32)], axis=1)
        out, self._state = self._session.run(
            None, {"input": x, "state": self._state, "sr": self._sr}
        )
        self._context = x[:, -_CONTEXT_SAMPLES:]
        return float(out[0][0])
