import httpx

from callback_voice.core.config.provider_config import ProviderChoice
from callback_voice.doctor.check_result import CheckResult

DEFAULT_OLLAMA_URL = "http://localhost:11434"


def check_ollama(choice: ProviderChoice) -> CheckResult:
    """Only runs when the configured caller LLM is Ollama."""
    if choice.name != "ollama":
        return CheckResult("local models", "ollama", "skip", f"caller LLM is {choice.name}")
    base_url = choice.base_url or DEFAULT_OLLAMA_URL
    try:
        response = httpx.get(f"{base_url}/api/tags", timeout=2.0)
        response.raise_for_status()
    except httpx.HTTPError:
        return CheckResult(
            "local models",
            "ollama",
            "warn",
            f"not reachable at {base_url}",
            "Install from https://ollama.com and run `ollama serve` (scripted callers still work)",
        )
    names = {m.get("name", "") for m in response.json().get("models", [])}
    if choice.model and choice.model not in names:
        return CheckResult(
            "local models",
            "ollama",
            "warn",
            f"running, but {choice.model} is not pulled",
            f"ollama pull {choice.model}",
        )
    return CheckResult("local models", "ollama", "ok", f"{choice.model} ready at {base_url}")
