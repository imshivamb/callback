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
from callback_voice.providers.vad.silero_vad import SileroVad
from callback_voice.scoring.score_call import score_call

CALL = Path(__file__).parents[1] / "fixtures" / "calls" / "turn_taking"
SEED = 8995698031481687592  # above 2**53: a JavaScript number would round it


def make_run(run_dir: Path) -> None:
    """A run as an older Callback wrote it: no speech timeline, no latency times."""
    call_dir = run_dir / "calls" / "turn-taking--t1"
    shutil.copytree(CALL, call_dir)
    score = score_call(call_dir, Thresholds(), SileroVad())
    metrics = [m.model_copy(update={"sample_times_s": []}) for m in score.metrics]
    trial = TrialResult(
        call_id="turn-taking--t1",
        scenario_id="turn-taking",
        trial=1,
        seed=SEED,
        passed=False,
        metrics=metrics,
        findings=score.findings,
        failure_reasons=["response_latency_p95_s 2.1 s > 1.5 s"],
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
    run = RunResult(
        run_id="20260927-000000",
        created_at=datetime.now(UTC),
        callback_version="test",
        agent_config_hash="h",
        mode="off",
        scenarios=[
            ScenarioResult(scenario_id="turn-taking", agent="a", passed=False, trials=[trial])
        ],
        passed=False,
        exit_code=1,
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
