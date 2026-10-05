"""The CI gate: a latency regression that stays under the absolute limit is still
caught against a saved baseline, and the same agent run again is not."""

import json
import os
import xml.etree.ElementTree as ET
from importlib.util import find_spec
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    find_spec("kokoro_onnx") is None or find_spec("faster_whisper") is None,
    reason='needs pip install "callback-voice[local]"',
)

SCENARIO = """
id: gate
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
expect:
  thresholds: {response_latency_p95_s: 1.5}
"""


def latest(project: Path) -> Path:
    return max((project / ".callback" / "runs").iterdir())


def test_injected_latency_regression_fails_against_the_baseline(
    run_cli, write, tmp_path, good_agent, slow_agent
) -> None:
    write(
        "callback.yaml",
        "targets:\n"
        f"  good: {{transport: websocket, url: '{good_agent.url}'}}\n"
        f"  slow: {{transport: websocket, url: '{slow_agent.url}'}}\n",
    )
    write("scenarios/gate.yaml", SCENARIO)

    # One throwaway call first: the first call after an agent starts is slower on a busy
    # machine, and a baseline recorded on it would hide the regression under test.
    warm = run_cli("run", "scenarios", "--trials", "1")
    assert warm.returncode in (0, 1), warm.stdout + warm.stderr
    first = run_cli("run", "scenarios")
    assert first.returncode == 0, first.stdout + first.stderr
    saved = run_cli("baseline", "save", "main")
    assert saved.returncode == 0, saved.stdout + saved.stderr
    assert (tmp_path / ".callback" / "baselines" / "main.json").is_file()

    again = run_cli("run", "scenarios", "--baseline", "main")
    assert again.returncode == 0, again.stdout + again.stderr
    same = json.loads((latest(tmp_path) / "results.json").read_text(encoding="utf-8"))
    assert same["baseline_name"] == "main" and same["baseline_diff"]
    assert not [d for d in same["baseline_diff"] if d["regressed"]], same["baseline_diff"]

    slow = run_cli("run", "scenarios", "--agent", "slow", "--baseline", "main")
    assert slow.returncode == 1, slow.stdout + slow.stderr
    assert "REGRESSED" in slow.stdout
    data = json.loads((latest(tmp_path) / "results.json").read_text(encoding="utf-8"))
    [scenario] = data["scenarios"]
    p95 = next(a for a in scenario["aggregates"] if a["name"] == "response_latency_p95_s")
    if not os.environ.get("CALLBACK_CI_LATENCY_LIMIT_S"):
        # Under the absolute 1.5 s limit, so only the baseline catches it. A slow CI
        # machine loosens that limit and puts the slowed agent near it, so there only
        # the regression below is checked.
        assert p95["passed"] is True, p95
    regressed = {d["metric"]: d for d in data["baseline_diff"] if d["regressed"]}
    assert "response_latency_p95_s" in regressed, data["baseline_diff"]
    assert regressed["response_latency_p95_s"]["delta"] >= 0.25

    junit = ET.parse(latest(tmp_path) / "junit.xml").getroot()
    failed = [c.get("name") for c in junit.iter("testcase") if c.find("failure") is not None]
    assert "baseline response_latency_p95_s" in failed
