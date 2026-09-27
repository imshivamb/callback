"""M6.1: each of the buggy agent's task bugs is caught by the end-state check on a real call,
the extra spoken facts are checked, and the privacy-leak pattern rule fires."""

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
BUGS = {
    "wrong_hour": "hour is 20, expected 19",
    "ignores_party_change": "party_size is 4, expected 5",
    "confirms_without_saving": "status is 'untouched', expected 'moved'",
}


@pytest.fixture
def project(tmp_path: Path, good_agent, buggy_agent) -> Path:
    shutil.copy(
        REPO / "scenarios/restaurant/move-and-resize.yaml", tmp_path / "move-and-resize.yaml"
    )
    targets = [f"  restaurant-good: {{transport: websocket, url: '{good_agent.url}'}}"]
    targets += [
        f"  {bug}: {{transport: websocket, url: '{buggy_agent.url}/?task_bug={bug}'}}"
        for bug in BUGS
    ]
    (tmp_path / "callback.yaml").write_text("targets:\n" + "\n".join(targets) + "\n")
    return tmp_path


def run(run_cli, project: Path, agent: str) -> dict:
    done = run_cli("run", "move-and-resize.yaml", "--agent", agent, cwd=project)
    run_dir = max((project / ".callback" / "runs").iterdir())
    trial = json.loads((run_dir / "results.json").read_text())["scenarios"][0]["trials"][0]
    return trial | {"_exit": done.returncode, "_stdout": done.stdout}


def metrics(trial: dict) -> dict:
    return {m["name"]: m for m in trial["metrics"]}


def test_good_agent_passes_state_facts_and_policy(run_cli, project) -> None:
    trial = run(run_cli, project, "restaurant-good")
    assert trial["_exit"] == 0, trial["_stdout"]
    m = metrics(trial)
    assert m["task_success"]["value"] == 1.0
    assert m["entity_fidelity"]["value"] == 1.0, m["entity_fidelity"]["detail"]
    assert m["policy_violations"]["value"] == 0


@pytest.mark.parametrize("bug", list(BUGS))
def test_each_task_bug_is_caught_by_the_end_state(run_cli, project, bug) -> None:
    trial = run(run_cli, project, bug)
    assert trial["_exit"] == 1, trial["_stdout"]
    m = metrics(trial)
    assert m["task_success"]["passed"] is False
    assert any(BUGS[bug] in r for r in trial["failure_reasons"]), trial["failure_reasons"]
    # The buggy profile also leaks another guest's booking; the pattern rule catches it.
    assert m["policy_violations"]["value"] >= 1, trial["findings"]
    leaks = [f["message"] for f in trial["findings"] if f["metric"] == "policy_violations"]
    assert any("another guest" in message for message in leaks)
