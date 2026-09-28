import os

import httpx

from callback_voice.core.config.provider_config import ProviderChoice
from callback_voice.doctor.check_result import CheckResult
from callback_voice.providers.llm.build_llm import KNOWN_ENDPOINTS

_GROUP = "caller llm"


def check_caller_llm(choice: ProviderChoice) -> CheckResult:
    """Is the persona/judge LLM reachable, and does it serve the configured model?

    Only the model list is requested, which is free. Scripted callers need no LLM,
    so a problem here is a warning, not a failure.
    """
    if choice.name == "ollama":
        return _check_ollama(choice)
    if choice.name == "anthropic":
        key_set = bool(os.environ.get("ANTHROPIC_API_KEY"))
        return CheckResult(
            _GROUP,
            "anthropic",
            "ok" if key_set else "warn",
            f"{choice.model}; key {'set' if key_set else 'not set'}",
            None if key_set else "export ANTHROPIC_API_KEY=... or `ant auth login`",
        )
    base_url, key_env, model = KNOWN_ENDPOINTS.get(choice.name, (None, None, None))
    base_url, key_env = choice.base_url or base_url, choice.api_key_env or key_env
    model = choice.model or model
    key = os.environ.get(key_env or "")
    if key_env and not key:
        return CheckResult(
            _GROUP,
            choice.name,
            "warn",
            f"${key_env} is not set (scripted callers still work)",
            f"export {key_env}=...  (free key: https://aistudio.google.com/apikey)"
            if choice.name == "gemini"
            else f"export {key_env}=...",
        )
    try:
        response = httpx.get(
            f"{base_url}/models",
            timeout=5.0,
            headers={"Authorization": f"Bearer {key}"} if key else {},
        )
    except httpx.HTTPError as exc:
        return CheckResult(_GROUP, choice.name, "warn", f"{base_url} not reachable: {exc}")
    if response.status_code in (401, 403):
        return CheckResult(_GROUP, choice.name, "warn", f"${key_env} was rejected", "check the key")
    if response.status_code >= 400:
        return CheckResult(
            _GROUP, choice.name, "warn", f"model list returned {response.status_code}"
        )
    served = {str(m.get("id", "")).removeprefix("models/") for m in response.json().get("data", [])}
    if model and served and model not in served:
        return CheckResult(
            _GROUP,
            choice.name,
            "warn",
            f"{model} is not offered by {choice.name}",
            "set providers.llm.model in callback.yaml",
        )
    return CheckResult(_GROUP, choice.name, "ok", f"{model} ready")


def _check_ollama(choice: ProviderChoice) -> CheckResult:
    base_url = choice.base_url or "http://localhost:11434"
    try:
        response = httpx.get(f"{base_url}/api/tags", timeout=2.0)
        response.raise_for_status()
    except httpx.HTTPError:
        return CheckResult(
            _GROUP,
            "ollama",
            "warn",
            f"not reachable at {base_url}",
            "install from https://ollama.com and run `ollama serve`",
        )
    names = {m.get("name", "") for m in response.json().get("models", [])}
    if choice.model and choice.model not in names:
        return CheckResult(
            _GROUP, "ollama", "warn", f"{choice.model} is not pulled", f"ollama pull {choice.model}"
        )
    return CheckResult(_GROUP, "ollama", "ok", f"{choice.model} ready at {base_url}")


def check_local_caller() -> CheckResult:
    """``callback run --local``: optional, so a missing Ollama is only a note."""
    from callback_voice.core.config.provider_config import LOCAL_CALLER_LLM

    result = _check_ollama(LOCAL_CALLER_LLM)
    return CheckResult(
        _GROUP,
        "ollama (--local)",
        "ok" if result.status == "ok" else "skip",
        result.detail if result.status == "ok" else f"optional; {result.detail}",
        None if result.status == "ok" else _local_fix(result),
    )


def _local_fix(result: CheckResult) -> str:
    from callback_voice.core.config.provider_config import LOCAL_CALLER_LLM

    if "not pulled" in result.detail:
        return f"ollama pull {LOCAL_CALLER_LLM.model}"
    return f"install from https://ollama.com, then: ollama pull {LOCAL_CALLER_LLM.model}"
