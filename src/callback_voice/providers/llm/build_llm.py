from typing import Final

from callback_voice.core.config.provider_config import ProviderChoice
from callback_voice.errors import ProviderError
from callback_voice.providers.llm.base import ChatModel

# OpenAI-compatible endpoints known by name, so callback.yaml can just say `name: gemini`.
KNOWN_ENDPOINTS: Final = {
    "gemini": (
        "https://generativelanguage.googleapis.com/v1beta/openai",
        "GEMINI_API_KEY",
        "gemini-flash-latest",
    ),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY", "llama-3.3-70b-versatile"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", None),
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY", None),
}


def build_llm(choice: ProviderChoice) -> ChatModel:
    """Create the configured chat model."""
    match choice.name:
        case "ollama":
            from callback_voice.providers.llm.ollama_llm import OllamaLlm

            return OllamaLlm(choice.model or "qwen3:4b", choice.base_url)
        case "anthropic":
            from callback_voice.providers.llm.anthropic_llm import DEFAULT_MODEL, AnthropicLlm

            return AnthropicLlm(choice.model or DEFAULT_MODEL, choice.usd_per_1k_tokens)
        case "openai-compatible" | "gemini" | "groq" | "openrouter" | "openai":
            from callback_voice.providers.llm.openai_compatible_llm import OpenAiCompatibleLlm

            base_url, key_env, model = KNOWN_ENDPOINTS.get(choice.name, (None, None, None))
            base_url, key_env = choice.base_url or base_url, choice.api_key_env or key_env
            model = choice.model or model
            if not model or not base_url:
                raise ProviderError(f"LLM provider {choice.name!r} needs model and base_url")
            return OpenAiCompatibleLlm(model, base_url, key_env, choice.usd_per_1k_tokens or 0.0)
        case other:
            raise ProviderError(
                f"unknown LLM provider {other!r}",
                hint="use gemini, groq, openrouter, openai, anthropic or ollama",
            )
