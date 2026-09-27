import httpx

from callback_voice.core.models.expectation import StateCheck
from callback_voice.core.models.verifier_result import VerifierResult
from callback_voice.errors import CallbackError
from callback_voice.scoring.verifiers.match_state import match_state


async def check_state(
    check: StateCheck, url: str, *, call_id: str, scenario_id: str, trial: int
) -> VerifierResult:
    """Ask the agent's system what actually happened, and compare it with ``match``.

    Run right after the call, while its state is fresh. An unreachable or broken
    webhook raises: the trial becomes an error (exit 2), never a silent pass or fail.
    """
    params = {"call_id": call_id, "scenario_id": scenario_id, "trial": str(trial)}
    try:
        async with httpx.AsyncClient(timeout=check.timeout_s) as client:
            response = await client.get(url, params=params)
    except httpx.HTTPError as exc:
        raise CallbackError(
            f"state webhook {url} failed: {exc!r}", hint="is the agent's verify endpoint running?"
        ) from exc
    if response.status_code >= 400:
        raise CallbackError(
            f"state webhook {url} returned {response.status_code}: {response.text[:200]}"
        )
    try:
        observed = response.json()
    except ValueError as exc:
        raise CallbackError(f"state webhook {url} did not return JSON") from exc
    if not isinstance(observed, dict):
        raise CallbackError(f"state webhook {url} must return a JSON object")

    problems = match_state(observed, check.match)
    detail = "end state matches" if not problems else "; ".join(problems)
    return VerifierResult(
        name="task_success", passed=not problems, detail=detail, observed=observed
    )
