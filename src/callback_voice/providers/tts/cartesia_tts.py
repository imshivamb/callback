import os

import httpx

from callback_voice.audio.format import SAMPLE_RATE, Audio
from callback_voice.audio.pcm import from_pcm16
from callback_voice.audio.trim_silence import trim_silence
from callback_voice.errors import ProviderError

_URL = "https://api.cartesia.ai/tts/bytes"
_VERSION = "2025-04-16"


class CartesiaTts:
    """Hosted TTS (optional, paid): low-latency Sonic voices."""

    name = "cartesia"

    def __init__(
        self,
        model: str = "sonic-2",
        default_voice: str = "a0e99841-438c-4a64-b679-ae501e7d6091",
        api_key_env: str = "CARTESIA_API_KEY",
    ) -> None:
        self._model = model
        self._default_voice = default_voice
        self._key_env = api_key_env

    @property
    def identity(self) -> str:
        return f"cartesia:{self._model}:{_VERSION}"

    async def synthesize(
        self, text: str, *, voice: str | None = None, speed: float = 1.0, language: str = "en"
    ) -> Audio:
        key = os.environ.get(self._key_env)
        if not key:
            raise ProviderError(f"${self._key_env} is not set", hint=f"export {self._key_env}=...")
        body = {
            "model_id": self._model,
            "transcript": text,
            "voice": {"mode": "id", "id": voice or self._default_voice},
            "language": language.split("-")[0],
            "output_format": {
                "container": "raw",
                "encoding": "pcm_s16le",
                "sample_rate": SAMPLE_RATE,
            },
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                _URL, json=body, headers={"X-API-Key": key, "Cartesia-Version": _VERSION}
            )
        if response.status_code >= 400:
            raise ProviderError(f"Cartesia returned {response.status_code}: {response.text[:200]}")
        return trim_silence(from_pcm16(response.content))
