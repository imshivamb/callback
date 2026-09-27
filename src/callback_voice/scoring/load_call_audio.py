from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from callback_voice.audio.format import SAMPLE_RATE, Audio
from callback_voice.errors import CallbackError


@dataclass(frozen=True, slots=True)
class CallAudio:
    caller_wire: Audio
    agent: Audio
    caller_clean: Audio

    @property
    def duration_s(self) -> float:
        return self.agent.size / SAMPLE_RATE


def load_call_audio(call_dir: Path) -> CallAudio:
    """Read ``call.wav`` (caller left, agent right) and ``caller_clean.wav``."""
    try:
        stereo, rate = sf.read(str(call_dir / "call.wav"), dtype="float32", always_2d=True)
        clean, clean_rate = sf.read(str(call_dir / "caller_clean.wav"), dtype="float32")
    except (OSError, RuntimeError) as exc:
        raise CallbackError(f"cannot read the recording in {call_dir}: {exc}") from exc
    if rate != SAMPLE_RATE or clean_rate != SAMPLE_RATE or stereo.shape[1] != 2:
        raise CallbackError(f"{call_dir}/call.wav must be 16 kHz stereo")
    return CallAudio(
        np.ascontiguousarray(stereo[:, 0]),
        np.ascontiguousarray(stereo[:, 1]),
        clean.astype(np.float32),
    )
