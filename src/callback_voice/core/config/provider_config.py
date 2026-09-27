from typing import Any

from pydantic import Field

from callback_voice.core.models.strict_model import StrictModel


class ProviderChoice(StrictModel):
    """One provider selection. Keys are never stored here, only the env var name."""

    name: str
    model: str | None = None
    voice: str | None = None
    base_url: str | None = None
    api_key_env: str | None = None
    usd_per_1k_tokens: float | None = Field(default=None, ge=0)
    options: dict[str, Any] = Field(default_factory=dict)


class ProvidersConfig(StrictModel):
    """Which implementation backs each interface.

    Speech runs locally for free. The caller/judge LLM defaults to Gemini's free
    tier; ``ollama`` keeps everything local.
    """

    stt: ProviderChoice = ProviderChoice(name="faster-whisper", model="base")
    scoring_stt: ProviderChoice = ProviderChoice(name="faster-whisper", model="small")
    tts: ProviderChoice = ProviderChoice(name="kokoro", voice="af_heart")
    llm: ProviderChoice = ProviderChoice(
        name="gemini", model="gemini-flash-lite-latest", api_key_env="GEMINI_API_KEY"
    )
    judge: ProviderChoice | None = None
    vad: ProviderChoice = ProviderChoice(name="silero")


LOCAL_PROVIDERS = ProvidersConfig()
