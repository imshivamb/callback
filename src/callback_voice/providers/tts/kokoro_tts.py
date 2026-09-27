import asyncio
from functools import cache
from typing import Any

import numpy as np

from callback_voice.audio.format import SAMPLE_RATE, Audio
from callback_voice.audio.resample import resample
from callback_voice.audio.trim_silence import trim_silence
from callback_voice.errors import ProviderUnavailableError
from callback_voice.providers.tts.find_espeak import find_espeak
from callback_voice.providers.tts.kokoro_files import MODEL_FILE, ensure_kokoro_files
from callback_voice.providers.tts.kokoro_voices import kokoro_lang, kokoro_voice

_KOKORO_RATE = 24_000


class KokoroTts:
    """Local Kokoro-82M (Apache-2.0 weights) via kokoro-onnx. Free; runs ~5x real time on CPU."""

    name = "kokoro"

    def __init__(self, default_voice: str = "af_heart") -> None:
        self._default_voice = default_voice

    @property
    def identity(self) -> str:
        return f"kokoro:{MODEL_FILE}"

    async def synthesize(
        self, text: str, *, voice: str | None = None, speed: float = 1.0, language: str = "en"
    ) -> Audio:
        engine = await asyncio.to_thread(
            _engine
        )  # first call loads the model; keep it off the loop
        samples, rate = await asyncio.to_thread(
            engine.create,
            text,
            voice=kokoro_voice(voice, self._default_voice),
            speed=float(np.clip(speed, 0.5, 2.0)),
            lang=kokoro_lang(language),
        )
        audio = resample(
            np.asarray(samples, dtype=np.float32), int(rate or _KOKORO_RATE), SAMPLE_RATE
        )
        return trim_silence(audio)


@cache
def _engine() -> Any:
    try:
        from kokoro_onnx import EspeakConfig, Kokoro  # type: ignore[attr-defined]
    except ImportError as exc:
        raise ProviderUnavailableError(
            "kokoro-onnx is not installed", hint='pip install "callback-voice[local]"'
        ) from exc
    espeak = find_espeak()
    if espeak is None:
        raise ProviderUnavailableError(
            "Kokoro needs espeak-ng and none was found",
            hint="brew install espeak-ng  (macOS)  |  apt install espeak-ng  (Linux)",
        )
    model, voices = ensure_kokoro_files()
    config = EspeakConfig(lib_path=espeak.library, data_path=espeak.data_path)
    return Kokoro(str(model), str(voices), espeak_config=config)
