from collections.abc import Mapping

from rich.text import Text

from callback_voice.core.models.run_result import RunResult
from callback_voice.core.runner.ci_limits import CI_LATENCY_ENV

_GUIDE = "https://github.com/imshivamb/callback/blob/main/docs/ci-example.md"


def ci_runner_hint(result: RunResult, env: Mapping[str, str], cpu_count: int | None) -> Text | None:
    """On GitHub Actions, explain a reply-delay failure that may be the runner's size.

    Shared runners are slower than a laptop and private repositories get half the
    cores, so an agent started inside the job can miss an absolute latency limit for
    reasons unrelated to the change. Nothing is loosened here: the hint names the
    runner's core count and the setting that would, if the user chooses to.
    """
    if env.get("GITHUB_ACTIONS") != "true":
        return None
    failed = [
        s.scenario_id
        for s in result.scenarios
        if (a := s.aggregate("response_latency_p95_s")) is not None and a.passed is False
    ]
    if not failed:
        return None
    cores = f"{cpu_count} CPU cores" if cpu_count else "an unknown number of CPU cores"
    current = env.get(CI_LATENCY_ENV)
    setting = (
        f"{CI_LATENCY_ENV} is already {current} s here"
        if current
        else f"If your agent runs inside this job, you can set {CI_LATENCY_ENV} to a limit "
        "taken from your own runs; it is recorded next to the real target"
    )
    return Text(
        f"▲ Reply delay failed on a GitHub Actions runner with {cores} "
        f"({', '.join(failed)}). Shared runners synthesise speech 2–3× slower than a "
        "laptop, and private repositories get smaller runners (2 cores, public ones 4). "
        f"{setting}. See {_GUIDE}\n",
        style="warn",
    )
