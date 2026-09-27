from callback_voice.core.config.provider_config import ProviderChoice
from callback_voice.errors import ProviderError
from callback_voice.providers.tts.base import TextToSpeech


def build_tts(choice: ProviderChoice) -> TextToSpeech:
    """Create the configured text-to-speech provider."""
    match choice.name:
        case "kokoro":
            from callback_voice.providers.tts.kokoro_tts import KokoroTts

            return KokoroTts(choice.voice or "af_heart")
        case "piper":
            from callback_voice.providers.tts.piper_tts import PiperTts

            return PiperTts(choice.voice or "en_US-lessac-medium")
        case "elevenlabs":
            from callback_voice.providers.tts.elevenlabs_tts import ElevenLabsTts

            return ElevenLabsTts(
                choice.model or "eleven_flash_v2_5",
                choice.voice or "21m00Tcm4TlvDq8ikWAM",
                choice.api_key_env or "ELEVENLABS_API_KEY",
            )
        case "cartesia":
            from callback_voice.providers.tts.cartesia_tts import CartesiaTts

            return CartesiaTts(
                choice.model or "sonic-2",
                choice.voice or "a0e99841-438c-4a64-b679-ae501e7d6091",
                choice.api_key_env or "CARTESIA_API_KEY",
            )
        case other:
            raise ProviderError(
                f"unknown TTS provider {other!r}", hint="use kokoro, piper, elevenlabs or cartesia"
            )
