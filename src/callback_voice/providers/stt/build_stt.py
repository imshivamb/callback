from callback_voice.core.config.provider_config import ProviderChoice
from callback_voice.errors import ProviderError
from callback_voice.providers.stt.base import SpeechToText


def build_stt(choice: ProviderChoice, *, words: bool = False, beam_size: int = 1) -> SpeechToText:
    """Create the configured speech-to-text provider."""
    match choice.name:
        case "faster-whisper":
            from callback_voice.providers.stt.faster_whisper_stt import FasterWhisperStt

            return FasterWhisperStt(
                choice.model or "base", words=words, beam_size=beam_size, **choice.options
            )
        case "deepgram":
            from callback_voice.providers.stt.deepgram_stt import DeepgramStt

            return DeepgramStt(choice.model or "nova-3", choice.api_key_env or "DEEPGRAM_API_KEY")
        case other:
            raise ProviderError(
                f"unknown STT provider {other!r}", hint="use faster-whisper or deepgram"
            )
