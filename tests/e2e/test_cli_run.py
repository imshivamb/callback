"""`callback run` end to end: real CLI, real agent process, real calls."""

import json
import os
from importlib.util import find_spec
from pathlib import Path

import pytest

needs_local = pytest.mark.skipif(
    find_spec("kokoro_onnx") is None or find_spec("faster_whisper") is None,
    reason='needs pip install "callback-voice[local]"',
)
needs_gemini = pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"), reason="needs GEMINI_API_KEY"
)

SCRIPTED = """
id: scripted-move
agent: restaurant
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
PERSONA = """
id: persona-move
agent: restaurant
max_duration_s: 180
caller:
  persona: "Priya Sharma, 34, friendly but busy"
  goal: "Move your Friday 8pm table for 4 to Saturday, any time between 7 and 9pm, and confirm it."
  knows: {name: Priya Sharma, booking_ref: DX7Q2, party_size: 4}
  voice: female_in_1
"""


def project(write, agent_url: str, scenario: str) -> None:
    write(
        "callback.yaml", f"targets:\n  restaurant: {{transport: websocket, url: '{agent_url}'}}\n"
    )
    write("scenarios/s.yaml", scenario)


def results(tmp_path: Path) -> dict:
    [run_dir] = list((tmp_path / ".callback" / "runs").iterdir())
    return json.loads((run_dir / "results.json").read_text())


@needs_local
def test_scripted_run_passes_and_writes_results(run_cli, write, tmp_path, good_agent) -> None:
    project(write, good_agent.url, SCRIPTED)
    done = run_cli("run", "scenarios")

    assert done.returncode == 0, done.stdout + done.stderr
    assert "PASS" in done.stdout and "no LLM calls" in done.stdout
    data = results(tmp_path)
    [scenario] = data["scenarios"]
    [trial] = scenario["trials"]
    assert trial["passed"] and trial["call"]["end_reason"] == "caller_hangup"
    names = {m["name"] for m in trial["metrics"]}
    assert {"response_latency_p95_s", "talk_over_ratio", "time_to_yield_p95_s"} <= names
    call_dir = tmp_path / ".callback" / "runs" / data["run_id"] / "calls" / trial["call_id"]
    assert {"call.wav", "caller_clean.wav", "events.jsonl"} <= {p.name for p in call_dir.iterdir()}
    assert good_agent.verify(trial["call_id"])["status"] == "moved"


def test_unreachable_agent_is_an_error_not_a_failure(run_cli, write) -> None:
    project(write, "ws://127.0.0.1:9", SCRIPTED)
    done = run_cli("run", "scenarios")
    assert done.returncode == 2, done.stdout
    assert "cannot connect" in done.stdout


@needs_local
@needs_gemini
def test_llm_caller_reaches_its_goal_then_replays_without_the_llm(
    run_cli, write, tmp_path, good_agent
) -> None:
    project(write, good_agent.url, PERSONA)

    recorded = run_cli("run", "scenarios", "--record")
    assert recorded.returncode == 0, recorded.stdout + recorded.stderr
    end_state = good_agent.verify("persona-move--t1")
    assert end_state["status"] == "moved" and end_state["day"] == "saturday", end_state
    assert 19 <= end_state["hour"] <= 21

    # Replay must not touch the LLM at all: prove it by removing the key.
    env_without_key = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
    import subprocess
    import sys

    replayed = subprocess.run(
        [sys.executable, "-m", "callback_voice.cli", "run", "scenarios", "--replay"],
        cwd=tmp_path,
        env=env_without_key,
        capture_output=True,
        text=True,
        check=False,
    )
    assert replayed.returncode == 0, replayed.stdout + replayed.stderr
    assert "no LLM calls" in replayed.stdout
