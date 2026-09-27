from typing import Protocol

from callback_voice.audio.format import Audio


class TextToSpeech(Protocol):
    """Synthesises one utterance to 16 kHz mono float, trimmed of edge silence.

    ``identity`` names everything that changes the audio besides the call
    arguments (provider, model, version) so caches never serve stale audio.
    """

    name: str

    @property
    def identity(self) -> str: ...

    async def synthesize(
        self, text: str, *, voice: str | None = None, speed: float = 1.0, language: str = "en"
    ) -> Audio: ...
