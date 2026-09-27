"""M5 gate: chaos against real agents. The good agent survives it, the buggy one is caught,
and a replayed call reproduces the original exactly."""

import json
import shutil
from importlib.util import find_spec
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(
    find_spec("kokoro_onnx") is None or find_spec("faster_whisper") is None,
    reason='needs pip install "callback-voice[local]"',
)


@pytest.fixture
def chaos_project(tmp_path: Path, good_agent, buggy_agent) -> Path:
    """The repo's chaos scenarios, pointed at freshly started good and buggy agents."""
    shutil.copytree(REPO / "scenarios" / "chaos", tmp_path / "chaos")
    (tmp_path / "callback.yaml").write_text(
        "targets:\n"
        f"  restaurant-good: {{transport: websocket, url: '{good_agent.url}'}}\n"
        f"  restaurant-buggy: {{transport: websocket, url: '{buggy_agent.url}'}}\n"
    )
    return tmp_path


def latest_results(project: Path) -> dict:
    run_dir = max((project / ".callback" / "runs").iterdir())
    return json.loads((run_dir / "results.json").read_text())


def metrics(results: dict, scenario_id: str) -> dict:
    [scenario] = [s for s in results["scenarios"] if s["scenario_id"] == scenario_id]
    return {m["name"]: m for m in scenario["trials"][0]["metrics"]}


def test_good_agent_survives_every_chaos_scenario(run_cli, chaos_project) -> None:
    done = run_cli("run", "chaos", cwd=chaos_project)
    assert done.returncode == 0, done.stdout + done.stderr
    results = latest_results(chaos_project)

    barge = metrics(results, "barge-in")["time_to_yield_p95_s"]
    assert barge["passed"] and len(barge["samples"]) == 1, barge
    assert metrics(results, "backchannel")["false_yields"]["value"] == 0
    assert metrics(results, "silent-caller")["silence_reprompt_s"]["passed"] is True
    assert metrics(results, "rough-line")["talk_over_ratio"]["passed"] is True
    assert all(
        m["chaos_drift_max_s"]["value"] is None or m["chaos_drift_max_s"]["value"] < 0.1
        for m in (metrics(results, s["scenario_id"]) for s in results["scenarios"])
    )

    rough = next(s for s in results["scenarios"] if s["scenario_id"] == "rough-line")
    kinds = {
        (e.get("chaos_type"), e.get("data", {}).get("phase"))
        for e in rough["trials"][0]["call"]["events"]
        if e["kind"] == "chaos"
    }
    assert {
        ("noise", None),
        ("packet_loss", "start"),
        ("packet_loss", "end"),
        ("jitter", None),
    } <= kinds


def test_buggy_agent_is_caught_by_each_chaos_scenario(run_cli, chaos_project) -> None:
    done = run_cli("run", "chaos", "--agent", "restaurant-buggy", cwd=chaos_project)
    assert done.returncode == 1, done.stdout + done.stderr
    results = latest_results(chaos_project)

    assert metrics(results, "barge-in")["time_to_yield_p95_s"]["passed"] is False
    assert metrics(results, "backchannel")["false_yields"]["passed"] is False
    assert metrics(results, "silent-caller")["silence_reprompt_s"]["passed"] is False
    silent = next(sc for sc in results["scenarios"] if sc["scenario_id"] == "silent-caller")
    assert any("never checked in" in r for r in silent["trials"][0]["failure_reasons"])


def test_replay_reproduces_the_call(run_cli, chaos_project) -> None:
    first = run_cli("run", "chaos/backchannel.yaml", cwd=chaos_project)
    assert first.returncode == 0, first.stdout
    replayed = run_cli("replay", "backchannel--t1", cwd=chaos_project)
    assert replayed.returncode == 0, replayed.stdout + replayed.stderr
    assert replayed.stdout.count("identical") == 2
