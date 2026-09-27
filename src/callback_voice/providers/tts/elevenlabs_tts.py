import os

import httpx
import numpy as np

from callback_voice.audio.format import SAMPLE_RATE, Audio
from callback_voice.audio.pcm import from_pcm16
from callback_voice.audio.trim_silence import trim_silence
from callback_voice.errors import ProviderError

_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice}"


class ElevenLabsTts:
    """Hosted TTS (optional, paid): more realistic callers, strong multilingual voices."""

    name = "elevenlabs"

    def __init__(
        self,
        model: str = "eleven_flash_v2_5",
        default_voice: str = "21m00Tcm4TlvDq8ikWAM",
        api_key_env: str = "ELEVENLABS_API_KEY",
    ) -> None:
        self._model = model
        self._default_voice = default_voice
        self._key_env = api_key_env

    @property
    def identity(self) -> str:
        return f"elevenlabs:{self._model}"

    async def synthesize(
        self, text: str, *, voice: str | None = None, speed: float = 1.0, language: str = "en"
    ) -> Audio:
        key = os.environ.get(self._key_env)
        if not key:
            raise ProviderError(f"${self._key_env} is not set", hint=f"export {self._key_env}=...")
        body = {
            "text": text,
            "model_id": self._model,
            "voice_settings": {"speed": float(np.clip(speed, 0.7, 1.2))},
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                _URL.format(voice=voice or self._default_voice),
                params={"output_format": f"pcm_{SAMPLE_RATE}"},
                json=body,
                headers={"xi-api-key": key},
            )
        if response.status_code >= 400:
            raise ProviderError(
                f"ElevenLabs returned {response.status_code}: {response.text[:200]}"
            )
        return trim_silence(from_pcm16(response.content))
