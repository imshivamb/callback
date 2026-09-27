import hashlib
from pathlib import Path

import numpy as np

from callback_voice.audio.format import Audio
from callback_voice.providers.tts.base import TextToSpeech


class CachedTts:
    """Wraps a TTS so identical utterances are synthesised once and reused from disk.

    Cache keys include the provider identity, voice, speed, language and text, so a
    model upgrade or voice change never replays stale audio.
    """

    def __init__(self, inner: TextToSpeech, directory: Path) -> None:
        self._inner = inner
        self._directory = directory
        self.name = inner.name
        self.hits = 0
        self.misses = 0

    @property
    def identity(self) -> str:
        return self._inner.identity

    @property
    def inner(self) -> TextToSpeech:
        """The uncached engine, e.g. to warm it up: a cache hit never loads the model."""
        return self._inner

    def key(self, text: str, *, voice: str | None, speed: float, language: str) -> str:
        material = "\x1f".join([self.identity, voice or "", f"{speed:.3f}", language, text])
        return hashlib.sha256(material.encode()).hexdigest()[:32]

    def lookup(
        self, text: str, *, voice: str | None = None, speed: float = 1.0, language: str = "en"
    ) -> Audio | None:
        """Cached audio or None, without synthesising (used by replay mode)."""
        path = self._path(self.key(text, voice=voice, speed=speed, language=language))
        return np.load(path).astype(np.float32) if path.is_file() else None

    async def synthesize(
        self, text: str, *, voice: str | None = None, speed: float = 1.0, language: str = "en"
    ) -> Audio:
        cached = self.lookup(text, voice=voice, speed=speed, language=language)
        if cached is not None:
            self.hits += 1
            return cached
        self.misses += 1
        audio = await self._inner.synthesize(text, voice=voice, speed=speed, language=language)
        path = self._path(self.key(text, voice=voice, speed=speed, language=language))
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp.npy")
        np.save(temp, audio.astype(np.float16))
        temp.replace(path)
        return audio

    def _path(self, key: str) -> Path:
        return self._directory / key[:2] / f"{key}.npy"
