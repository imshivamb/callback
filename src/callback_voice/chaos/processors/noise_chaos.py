from pathlib import Path

import numpy as np

from callback_voice.audio.format import FRAME_SAMPLES, Audio
from callback_voice.audio.normalize_loudness import TARGET_SPEECH_DBFS
from callback_voice.chaos.noise_beds.load_bed import load_bed
from callback_voice.chaos.params.noise import NoiseParams
from callback_voice.chaos.processors.chaos_context import ChaosContext
from callback_voice.chaos.processors.chaos_processor import ChaosProcessor
from callback_voice.core.models.chaos_event import ChaosEvent


class NoiseChaos(ChaosProcessor):
    """A background bed under the caller for the whole call, at ``snr_db`` below speech.

    Caller speech is normalised to a fixed level, so the SNR is exact.
    """

    def __init__(
        self, event: ChaosEvent, params: NoiseParams, rng: np.random.Generator, base_dir: Path
    ) -> None:
        self._event = event
        speech_rms = 10 ** (TARGET_SPEECH_DBFS / 20)
        self._bed = load_bed(params.bed, rng, base_dir) * speech_rms / 10 ** (params.snr_db / 20)
        self._pos = int(rng.integers(0, max(1, self._bed.size - FRAME_SAMPLES)))
        self._params = params
        self._noted = False

    def shape_outbound(self, ctx: ChaosContext, frame: Audio) -> Audio:
        if not self._noted:
            self._noted = True
            ctx.note(self._event, ctx.t_s, bed=self._params.bed, snr_db=self._params.snr_db)
        end = self._pos + frame.size
        if end > self._bed.size:
            self._pos, end = 0, frame.size
        noisy = frame + self._bed[self._pos : end]
        self._pos = end
        return noisy.astype(np.float32)
