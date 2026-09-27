import os

from callback_voice.core.config.provider_config import ProvidersConfig
from callback_voice.doctor.check_result import CheckResult


def check_api_keys(providers: ProvidersConfig) -> list[CheckResult]:
    """Report which configured hosted providers have their key env var set.

    Only names are checked; values are never read into output.
    """
    results: list[CheckResult] = []
    for role, choice in providers.model_dump(exclude_none=True).items():
        env = choice.get("api_key_env")
        if role == "llm":
            continue  # covered, with a live model check, by check_caller_llm
        if not env:
            continue
        name = f"{role}: {choice['name']}"
        if os.environ.get(env):
            results.append(CheckResult("keys", name, "ok", f"${env} is set"))
        else:
            results.append(
                CheckResult("keys", name, "warn", f"${env} is not set", f"export {env}=...")
            )
    if not results:
        results.append(
            CheckResult(
                "keys", "hosted providers", "skip", "none configured; local path needs no keys"
            )
        )
    return results
