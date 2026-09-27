from dataclasses import dataclass
from pathlib import Path

import numpy as np

from callback_voice.audio.format import FRAME_SAMPLES, Audio
from callback_voice.audio.tape import AudioTape
from callback_voice.audio.wav import write_wav


@dataclass(frozen=True, slots=True)
class RecordingPaths:
    stereo: Path
    caller_clean: Path


class CallRecorder:
    """Records every tick of a call.

    Channel 0 is the caller exactly as sent on the wire (after chaos: noise, loss,
    jitter). Channel 1 is the agent exactly as the caller heard it (after the
    playout buffer). Both are written at ``tick * 20 ms``, so they share one clock
    by construction. A third stem holds the caller's clean speech: ground truth for
    when the caller spoke, unaffected by the noise bed.
    """

    def __init__(self) -> None:
        self.caller = AudioTape()
        self.agent = AudioTape()
        self.caller_clean = AudioTape()

    def record_tick(
        self, tick: int, *, caller_wire: Audio, caller_clean: Audio, agent_heard: Audio
    ) -> None:
        at = tick * FRAME_SAMPLES
        self.caller.write_at(at, caller_wire)
        self.caller_clean.write_at(at, caller_clean)
        self.agent.write_at(at, agent_heard)

    def mix_caller(self, tick: int, audio: Audio) -> None:
        """Overlay audio that reached the wire late (jitter) onto the caller channel."""
        self.caller.write_at(tick * FRAME_SAMPLES, audio, mix=True)

    def save(self, directory: Path) -> RecordingPaths:
        caller, agent = self.caller.to_array(), self.agent.to_array()
        length = max(caller.size, agent.size)
        stereo = np.zeros((length, 2), dtype=np.float32)
        stereo[: caller.size, 0] = caller
        stereo[: agent.size, 1] = agent
        paths = RecordingPaths(directory / "call.wav", directory / "caller_clean.wav")
        write_wav(paths.stereo, np.clip(stereo, -1.0, 1.0))
        write_wav(paths.caller_clean, np.clip(self.caller_clean.to_array(), -1.0, 1.0))
        return paths
