"""The HTML report: one self-contained file built from a run's results and recordings."""

import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

from callback_voice.core.models.call_record import CallRecord
from callback_voice.core.models.run_result import RunResult
from callback_voice.core.models.scenario_result import ScenarioResult
from callback_voice.core.models.thresholds import Thresholds
from callback_voice.core.models.trial_result import TrialResult
from callback_voice.core.runner.scenario_verdict import scenario_verdict
from callback_voice.providers.vad.silero_vad import SileroVad
from callback_voice.scoring.aggregate.aggregate_scenario import aggregate_scenario
from callback_voice.scoring.score_call import score_call

CALL = Path(__file__).parents[1] / "fixtures" / "calls" / "turn_taking"
SEED = 8995698031481687592  # above 2**53: a JavaScript number would round it


def make_run(run_dir: Path, *, older: bool = True, limit_s: float = 1.5) -> None:
    """A run of the ``turn_taking`` fixture call (replies after 0.45, 1.2 and 2.1 s).

    ``older``: as an older Callback wrote it, with no speech timeline, no latency times
    and no across-call numbers. Otherwise as today, judged against ``limit_s``.
    """
    call_dir = run_dir / "calls" / "turn-taking--t1"
    shutil.copytree(CALL, call_dir)
    thresholds = Thresholds(response_latency_p95_s=limit_s)
    score = score_call(call_dir, thresholds, SileroVad())
    metrics = (
        [m.model_copy(update={"sample_times_s": []}) for m in score.metrics]
        if older
        else score.metrics
    )
    failed = [m for m in metrics if m.passed is False]
    trial = TrialResult(
        call_id="turn-taking--t1",
        scenario_id="turn-taking",
        trial=1,
        seed=SEED,
        passed=not failed,
        metrics=metrics,
        findings=score.findings,
        failure_reasons=[f"{m.name} {m.value} s > {m.threshold} s" for m in failed],
        call=CallRecord(
            call_id="turn-taking--t1",
            scenario_id="turn-taking",
            trial=1,
            seed=SEED,
            transport="websocket",
            started_at=datetime.now(UTC),
            duration_s=score.timeline.duration_s,
            end_reason="caller_hangup",
            wav_path="calls/turn-taking--t1/call.wav",
        ),
    )
    aggregates = [] if older else aggregate_scenario([trial], thresholds, seed=0)
    passed, reasons = scenario_verdict([trial], aggregates) if not older else (False, [])
    scenario = ScenarioResult(
        scenario_id="turn-taking",
        agent="a",
        passed=passed,
        trials=[trial],
        aggregates=aggregates,
        failure_reasons=reasons,
    )
    run = RunResult(
        run_id="20260927-000000",
        created_at=datetime.now(UTC),
        callback_version="test",
        agent_config_hash="h",
        mode="off",
        scenarios=[scenario],
        passed=passed,
        exit_code=0 if passed else 1,
    )
    (run_dir / "results.json").write_text(run.model_dump_json(), encoding="utf-8")


def embedded(page: str) -> dict:
    match = re.search(
        r'<script id="report-data" type="application/json">(.*?)</script>', page, re.S
    )
    assert match, "report data block missing"
    return json.loads(match.group(1))


def test_report_is_self_contained_and_draws_what_was_measured(run_cli, tmp_path) -> None:
    run_dir = tmp_path / "run"
    make_run(run_dir)

    done = run_cli("report", str(run_dir))
    assert done.returncode == 0, done.stdout + done.stderr
    page = (run_dir / "report.html").read_text(encoding="utf-8")
    assert not re.search(r"<(script|link)[^>]+(src|href)=", page), "must not load anything"
    [call] = embedded(page)["scenarios"][0]["calls"]

    assert call["seed"] == str(SEED)
    assert call["audio"].startswith("data:audio/mpeg;base64,")
    assert call["peaks"]["caller"] and call["peaks"]["agent"]
    assert call["remeasured"] and {t["who"] for t in call["speech"]} == {"caller", "agent"}
    truth = json.loads((CALL / "truth.json").read_text())["response_latencies_s"]
    measured = [p["v"] for p in call["latency"]]
    assert len(measured) == len(truth)
    assert all(abs(m - t) <= 0.05 for m, t in zip(measured, truth, strict=True)), measured


def test_report_without_audio_and_missing_run(run_cli, tmp_path) -> None:
    run_dir = tmp_path / "run"
    make_run(run_dir)
    done = run_cli("report", str(run_dir), "--no-audio")
    assert done.returncode == 0, done.stderr
    [call] = embedded((run_dir / "report.html").read_text())["scenarios"][0]["calls"]
    assert "audio" not in call and call["peaks"]["agent"]

    missing = run_cli("report", str(tmp_path / "nope"))
    assert missing.returncode == 2 and "no results.json" in missing.stderr


def test_summary_sentence_and_tiles_say_what_went_wrong(run_cli, tmp_path) -> None:
    failing, passing, older = tmp_path / "failing", tmp_path / "passing", tmp_path / "older"
    make_run(failing, older=False)
    make_run(passing, older=False, limit_s=5.0)
    make_run(older)
    for run_dir in (failing, passing, older):
        done = run_cli("report", str(run_dir), "--no-audio")
        assert done.returncode == 0, done.stderr

    data = embedded((failing / "report.html").read_text())
    assert data["summary"]["sentence"] == "The agent replies too slowly (2.01 s vs a 1.5 s limit)."
    [tile] = data["summary"]["tiles"]
    assert (
        tile["title"] == "Replies too slowly" and tile["detail"] == "1 of 3 replies over the limit"
    )
    assert tile["call_id"] == "turn-taking--t1" and tile["t_s"] is not None  # "Hear it" target
    assert data["scenarios"][0]["sentence"] == data["summary"]["sentence"]

    ok = embedded((passing / "report.html").read_text())["summary"]
    assert ok == {"sentence": "The agent passed every check in 1 call.", "tiles": []}

    old = embedded((older / "report.html").read_text())["summary"]["sentence"]
    assert "passed" not in old and "fails checks in 1 of 1 call (" in old, old
