from callback_voice.core.config.provider_config import ProviderChoice
from callback_voice.errors import ProviderError
from callback_voice.providers.vad.base import VoiceActivityModel


def build_vad(choice: ProviderChoice) -> VoiceActivityModel:
    """Create a fresh VAD model instance (models are stateful: one per stream)."""
    match choice.name:
        case "silero":
            from callback_voice.providers.vad.silero_vad import SileroVad

            return SileroVad()
        case "energy":
            from callback_voice.providers.vad.energy_vad import EnergyVad

            return EnergyVad(**choice.options)
        case other:
            raise ProviderError(f"unknown VAD provider {other!r}", hint="use silero or energy")
