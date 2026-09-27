import asyncio
from functools import cache
from typing import Any

import numpy as np

from callback_voice.audio.format import SAMPLE_RATE, Audio
from callback_voice.audio.resample import resample
from callback_voice.audio.trim_silence import trim_silence
from callback_voice.core.paths import model_cache_dir
from callback_voice.errors import ProviderUnavailableError


class PiperTts:
    """Local Piper voices. Opt-in extra: piper-tts is GPL-3.0 (see docs/licensing.md)."""

    name = "piper"

    def __init__(self, default_voice: str = "en_US-lessac-medium") -> None:
        self._default_voice = default_voice

    @property
    def identity(self) -> str:
        return "piper:1"

    async def synthesize(
        self, text: str, *, voice: str | None = None, speed: float = 1.0, language: str = "en"
    ) -> Audio:
        engine = _voice(voice or self._default_voice)
        return await asyncio.to_thread(_render, engine, text, speed)


def _render(engine: Any, text: str, speed: float) -> Audio:
    from piper import SynthesisConfig

    config = SynthesisConfig(length_scale=1.0 / max(speed, 0.5))
    chunks = [c.audio_float_array for c in engine.synthesize(text, syn_config=config)]
    audio = np.concatenate(chunks).astype(np.float32) if chunks else np.zeros(0, np.float32)
    return trim_silence(resample(audio, engine.config.sample_rate, SAMPLE_RATE))


@cache
def _voice(name: str) -> Any:
    try:
        from piper import PiperVoice
        from piper.download_voices import download_voice
    except ImportError as exc:
        raise ProviderUnavailableError(
            "piper-tts is not installed", hint='pip install "callback-voice[piper]"'
        ) from exc
    directory = model_cache_dir() / "piper"
    directory.mkdir(parents=True, exist_ok=True)
    model = directory / f"{name}.onnx"
    if not model.exists():
        download_voice(name, directory)
    return PiperVoice.load(model)
