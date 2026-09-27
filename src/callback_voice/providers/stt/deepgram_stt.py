import os

import httpx

from callback_voice.audio.format import SAMPLE_RATE, Audio
from callback_voice.audio.pcm import to_pcm16
from callback_voice.errors import ProviderError
from callback_voice.providers.stt.base import Transcript, Word

_URL = "https://api.deepgram.com/v1/listen"


class DeepgramStt:
    """Hosted STT (optional, paid). Pre-recorded endpoint; one request per utterance."""

    def __init__(self, model: str = "nova-3", api_key_env: str = "DEEPGRAM_API_KEY") -> None:
        self.name = f"deepgram:{model}"
        self._model = model
        self._key_env = api_key_env

    async def transcribe(self, audio: Audio, *, language: str | None = None) -> Transcript:
        key = os.environ.get(self._key_env)
        if not key:
            raise ProviderError(f"${self._key_env} is not set", hint=f"export {self._key_env}=...")
        params = {
            "model": self._model,
            "encoding": "linear16",
            "sample_rate": str(SAMPLE_RATE),
            "punctuate": "true",
            "smart_format": "false",
        }
        params["language"] = "multi" if language in {"hi-en", None} else language.split("-")[0]
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                _URL,
                params=params,
                content=to_pcm16(audio),
                headers={"Authorization": f"Token {key}", "Content-Type": "audio/l16"},
            )
        if response.status_code >= 400:
            raise ProviderError(f"Deepgram returned {response.status_code}: {response.text[:200]}")
        alt = response.json()["results"]["channels"][0]["alternatives"][0]
        words = tuple(Word(w["word"], w["start"], w["end"]) for w in alt.get("words", []))
        return Transcript(alt.get("transcript", ""), language, words)
