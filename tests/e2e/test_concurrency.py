"""Parallel calls: results stay in plan order with the same seeds, and a baseline made
at another concurrency is flagged, because parallel calls inflate latency."""

import json
from importlib.util import find_spec

import pytest

from callback_voice.core.seeds.derive_seed import derive_seed

pytestmark = pytest.mark.skipif(
    find_spec("kokoro_onnx") is None or find_spec("faster_whisper") is None,
    reason='needs pip install "callback-voice[local]"',
)

SCENARIO = """
id: parallel
agent: good
trials: 3
max_duration_s: 120
caller:
  persona: Arjun
  goal: move booking DX7Q2 to Saturday evening
  voice: male_us_1
  script:
    - "Hi, I need to move my booking to Saturday."
    - "It's D X 7 Q 2."
    - "Anytime between seven and nine is fine."
    - "Seven thirty works."
    - "Yes please."
    - "No, that's all. Thanks, bye."
"""


def test_three_calls_at_once_keep_order_seeds_and_record_concurrency(
    run_cli, write, tmp_path, good_agent
) -> None:
    write(
        "parallel.yaml",
        f"targets:\n  good: {{transport: websocket, url: '{good_agent.url}'}}\nconcurrency: 3\n",
    )
    write("scenarios/parallel.yaml", SCENARIO)

    done = run_cli("run", "scenarios", "--config", "parallel.yaml")
    assert done.returncode in (0, 1), done.stdout + done.stderr  # latency may inflate
    [run_dir] = list((tmp_path / ".callback" / "runs").iterdir())
    results = json.loads((run_dir / "results.json").read_text())
    assert results["concurrency"] == 3
    trials = results["scenarios"][0]["trials"]
    assert [t["trial"] for t in trials] == [1, 2, 3]
    assert [t["seed"] for t in trials] == [derive_seed(0, "parallel", n) for n in (1, 2, 3)]
    assert all(t["error"] is None and t["call"]["end_reason"] == "caller_hangup" for t in trials)

    assert run_cli("baseline", "save", "par", "--config", "parallel.yaml").returncode == 0
    write("serial.yaml", "targets:\n  good: {transport: websocket, url: 'ws://127.0.0.1:9'}\n")
    compared = run_cli("run", "scenarios", "--config", "serial.yaml", "--baseline", "par")
    assert "was run with concurrency 3, this run uses 1" in compared.stdout, compared.stdout
