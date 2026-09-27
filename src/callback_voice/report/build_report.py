from pathlib import Path
from typing import Any

from callback_voice.core.models.run_result import RunResult
from callback_voice.report.call_view import call_view


def build_report(result: RunResult, run_dir: Path, *, audio: bool = True) -> dict[str, Any]:
    """The report's data: the run verdict, every scenario's aggregates and baseline
    comparison, and every call's timeline, findings, waveform and audio."""
    return {
        "run": {
            "run_id": result.run_id,
            "created_at": result.created_at.isoformat(),
            "callback_version": result.callback_version,
            "git_sha": result.git_sha,
            "mode": result.mode,
            "duration_s": result.duration_s,
            "exit_code": result.exit_code,
            "passed": result.passed,
            "baseline_name": result.baseline_name,
            "providers": result.providers,
            "vad": result.vad,
            "judge": result.judge,
        },
        "scenarios": [
            {
                "scenario_id": s.scenario_id,
                "agent": s.agent,
                "passed": s.passed,
                "failure_reasons": s.failure_reasons,
                "aggregates": [a.model_dump() for a in s.aggregates],
                "baseline": [
                    d.model_dump(mode="json")
                    for d in result.baseline_diff
                    if d.scenario_id == s.scenario_id
                ],
                "calls": [call_view(t, run_dir, audio=audio) for t in s.trials],
            }
            for s in result.scenarios
        ],
    }
