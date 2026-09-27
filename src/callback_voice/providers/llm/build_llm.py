from callback_voice.core.config.provider_config import ProviderChoice
from callback_voice.errors import ProviderError
from callback_voice.providers.llm.base import ChatModel


def build_llm(choice: ProviderChoice) -> ChatModel:
    """Create the configured chat model."""
    match choice.name:
        case "ollama":
            from callback_voice.providers.llm.ollama_llm import OllamaLlm

            return OllamaLlm(choice.model or "qwen3:4b", choice.base_url)
        case "anthropic":
            from callback_voice.providers.llm.anthropic_llm import DEFAULT_MODEL, AnthropicLlm

            return AnthropicLlm(choice.model or DEFAULT_MODEL, choice.usd_per_1k_tokens)
        case "openai-compatible" | "openai" | "groq" | "gemini" | "openrouter":
            from callback_voice.providers.llm.openai_compatible_llm import OpenAiCompatibleLlm

            if not choice.model or not choice.base_url:
                raise ProviderError(f"LLM provider {choice.name!r} needs model and base_url")
            return OpenAiCompatibleLlm(
                choice.model, choice.base_url, choice.api_key_env, choice.usd_per_1k_tokens or 0.0
            )
        case other:
            raise ProviderError(
                f"unknown LLM provider {other!r}", hint="use ollama, anthropic or openai-compatible"
            )
