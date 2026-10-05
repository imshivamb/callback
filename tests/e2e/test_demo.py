"""`callback demo`: one command, no keys, the buggy agent caught and a report written."""

import json
from importlib.util import find_spec

import pytest

HAS_LOCAL = find_spec("kokoro_onnx") is not None and find_spec("faster_whisper") is not None


@pytest.mark.skipif(not HAS_LOCAL, reason='needs pip install "callback-voice[local]"')
def test_demo_catches_the_buggy_agent_and_writes_a_report(run_cli, tmp_path) -> None:
    done = run_cli("demo", "--no-open")
    assert done.returncode == 1, done.stdout + done.stderr
    [run_dir] = list((tmp_path / ".callback" / "runs").iterdir())
    assert (run_dir / "report.html").is_file() and (run_dir / "junit.xml").is_file()
    results = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    scenarios = {s["scenario_id"]: s for s in results["scenarios"]}
    assert set(scenarios) == {"barge-in", "backchannel"}
    barge = {a["name"]: a for a in scenarios["barge-in"]["aggregates"]}
    assert barge["time_to_yield_p95_s"]["passed"] is False
    backchannel = {a["name"]: a for a in scenarios["backchannel"]["aggregates"]}
    assert backchannel["false_yields"]["passed"] is False


@pytest.mark.skipif(HAS_LOCAL, reason="checks the message shown when the extra is missing")
def test_demo_without_local_speech_says_how_to_install(run_cli) -> None:
    done = run_cli("demo", "--no-open")
    assert done.returncode == 2
    assert 'pip install "callback-voice[local]"' in done.stderr
