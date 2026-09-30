"""Real end state, spoken entities, policy rules and the optional judge, end to end."""

import json
import os
from importlib.util import find_spec
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    find_spec("kokoro_onnx") is None or find_spec("faster_whisper") is None,
    reason='needs pip install "callback-voice[local]"',
)

SCRIPT = """
  script:
    - "Hi, I need to move my booking to Saturday."
    - "It's D X 7 Q 2."
    - "Anytime between seven and nine is fine."
    - "Seven thirty works."
    - "Yes please."
    - "No, that's all. Thanks, bye."
"""
CALLER = (
    "caller:\n  persona: Arjun\n  goal: move booking DX7Q2 to Saturday evening\n  voice: male_us_1\n"
    + SCRIPT
)


def scenario(scenario_id: str, match: str, webhook: str = "/verify") -> str:
    return f"""id: {scenario_id}
agent: restaurant
max_duration_s: 120
{CALLER}
expect:
  state: {{webhook: "{webhook}", match: {match}}}
  entities_spoken: ["DX7Q2"]
  must_not:
    - {{says: "\\\\bthe \\\\w+ party (already )?(has|is booked)", why: "reveals another guest's booking"}}
    - "Reveal another guest's booking"
"""


def project(tmp_path: Path, agent_url: str, *, judge: bool = False) -> None:
    judge_line = "providers:\n  judge: {name: gemini}\n" if judge else ""
    (tmp_path / "callback.yaml").write_text(
        f"targets:\n  restaurant: {{transport: websocket, url: '{agent_url}'}}\n{judge_line}"
    )


def trials(tmp_path: Path) -> dict[str, dict]:
    run_dir = max((tmp_path / ".callback" / "runs").iterdir())
    result = json.loads((run_dir / "results.json").read_text())
    return {s["scenario_id"]: s["trials"][0] | {"_run": result} for s in result["scenarios"]}


def metrics(trial: dict) -> dict[str, dict]:
    return {m["name"]: m for m in trial["metrics"]}


def test_good_agent_passes_state_entity_and_policy_checks(
    run_cli, write, tmp_path, good_agent
) -> None:
    judge = bool(os.environ.get("GEMINI_API_KEY"))
    project(tmp_path, good_agent.url, judge=judge)
    write(
        "s/moved.yaml", scenario("moved", "{status: moved, day: saturday, hour_between: [19, 21]}")
    )
    write("s/wrong-time.yaml", scenario("wrong-time", "{status: moved, hour: 20}"))

    done = run_cli("run", "s")
    assert done.returncode == 1, done.stdout  # wrong-time is expected to fail
    by_id = trials(tmp_path)

    moved = metrics(by_id["moved"])
    assert moved["task_success"]["value"] == 1.0
    assert moved["entity_fidelity"]["value"] == 1.0, by_id["moved"]["findings"]
    assert moved["policy_violations"]["value"] == 0
    assert by_id["moved"]["passed"], by_id["moved"]["failure_reasons"]
    agent_words = " ".join(
        t["text"] for t in by_id["moved"]["call"]["transcript"] if t["speaker"] == "agent"
    )
    assert "Olive" in agent_words
    [verifier] = by_id["moved"]["verifier_results"]
    assert verifier["observed"]["day"] == "saturday"

    wrong = by_id["wrong-time"]
    assert metrics(wrong)["task_success"]["passed"] is False
    assert any("hour is 19, expected 20" in r for r in wrong["failure_reasons"]), wrong[
        "failure_reasons"
    ]

    if judge:
        assert by_id["moved"]["_run"]["judge"]["prompt_version"] == "judge-v1"
        judged = [m for m in by_id["moved"]["metrics"] if m["method"] == "judge"]
        assert judged and all(m["passed"] is None for m in judged)


def test_buggy_agent_garbled_code_is_caught(run_cli, write, tmp_path, buggy_agent) -> None:
    project(tmp_path, buggy_agent.url)
    write("s/moved.yaml", scenario("moved", "{status: moved, day: saturday}"))

    done = run_cli("run", "s")
    assert done.returncode == 1, done.stdout
    trial = trials(tmp_path)["moved"]
    assert metrics(trial)["entity_fidelity"]["passed"] is False
    messages = [f["message"] for f in trial["findings"] if f["metric"] == "entity_fidelity"]
    assert any("B X 7 Q 2" in m and "D X 7 Q 2" in m for m in messages), messages


def test_unreachable_webhook_is_an_error(run_cli, write, tmp_path, good_agent) -> None:
    project(tmp_path, good_agent.url)
    short = scenario("bye", "{status: moved}", webhook="http://127.0.0.1:9/verify").replace(
        SCRIPT, '\n  script:\n    - "No thanks, that\'s all. Bye."\n'
    )
    write("s/bye.yaml", short)

    done = run_cli("run", "s")
    assert done.returncode == 2, done.stdout
    assert "state webhook" in done.stdout
