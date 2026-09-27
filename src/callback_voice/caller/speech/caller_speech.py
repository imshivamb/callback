from callback_voice.audio.format import Audio
from callback_voice.audio.normalize_loudness import normalize_loudness
from callback_voice.core.models.caller_spec import CallerSpec
from callback_voice.providers.tts.base import TextToSpeech


class CallerSpeech:
    """Renders the persona's lines in its voice, rate and language at a fixed level."""

    def __init__(self, tts: TextToSpeech, spec: CallerSpec) -> None:
        self._tts = tts
        self._spec = spec
        self.rate = spec.speaking_rate

    async def render(self, text: str) -> Audio:
        audio = await self._tts.synthesize(
            text, voice=self._spec.voice, speed=self.rate, language=self._spec.language
        )
        return normalize_loudness(audio)
