"""The CLI contract: commands, messages and exit codes (0 pass, 1 fail, 2 error)."""

import pytest

SPEC_EXAMPLE = """
id: move-dinner-booking-hinglish-noisy
agent: restaurant-reservations
trials: 5
caller:
  persona: "Priya, 34, calling from a busy street, in a hurry"
  goal: "Move Friday 8pm table for 4 to Saturday, any time 7-9pm"
  knows: {name: Priya Sharma, booking_ref: "DX7Q2", party_size: 4}
  language: hi-en
  patience: low
chaos:
  noise: {bed: street, snr_db: 10}
  events:
    - barge_in: {on: agent_turn, turn: 2, after_s: 0.8, say: "haan haan, Saturday"}
    - backchannel: {on: agent_turn, every: 1, say: ["hmm", "okay"]}
    - change_mind: {on: caller_turn, turn: 4, say: "actually make it 5 people"}
    - silence: {on: caller_turn, turn: 3, duration_s: 6}
    - packet_loss: {pct: 3, from_s: 30, to_s: 60}
expect:
  state: {webhook: "http://localhost:8765/verify", match: {status: moved, day: saturday}}
  entities_spoken: ["DX7Q2"]
  thresholds: {response_latency_p95_s: 1.5, time_to_yield_p95_s: 0.6}
"""
CONFIG = "targets:\n  restaurant-reservations: {transport: websocket, url: 'ws://127.0.0.1:8765'}\n"


def test_version(run_cli) -> None:
    done = run_cli("--version")
    assert done.returncode == 0 and done.stdout.startswith("callback ")


def test_doctor_runs_without_any_keys(run_cli) -> None:
    done = run_cli("doctor")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "silero-vad" in done.stdout and "caller llm" in done.stdout.lower()


def test_spec_example_scenario_validates(run_cli, write) -> None:
    write("callback.yaml", CONFIG)
    write("scenarios/move.yaml", SPEC_EXAMPLE)
    done = run_cli("validate", "scenarios")
    assert done.returncode == 0, done.stderr
    assert "move-dinner-booking-hinglish-noisy" in done.stdout and "5 trial(s)" in done.stdout


@pytest.mark.parametrize(
    ("event", "message"),
    [
        ("- teleport: {}", "unknown chaos event 'teleport'"),
        ("- barge_in: {on: caller_turn, turn: 1, say: hi}", "cannot trigger on caller_turn"),
        ("- barge_in: {say: hi}", "needs a trigger"),
        (
            "- barge_in: {on: agent_turn, turn: 1, every: 2, say: hi}",
            "exactly one of turn or every",
        ),
        ("- packet_loss: {pct: 3, on: agent_turn, turn: 1}", "takes no trigger"),
        ("- packet_loss: {pct: 3, from_s: 9, to_s: 2}", "to_s must be after from_s"),
    ],
)
def test_invalid_chaos_exits_2_with_the_exact_problem(
    run_cli, write, event: str, message: str
) -> None:
    write("callback.yaml", CONFIG)
    write(
        "bad.yaml",
        "id: x\nagent: restaurant-reservations\ncaller: {persona: p, goal: g}\n"
        f"chaos:\n  events:\n    {event}\n",
    )
    done = run_cli("validate", "bad.yaml")
    assert done.returncode == 2
    assert message in done.stderr and "bad.yaml" in done.stderr


def test_every_bad_file_and_duplicate_ids_are_reported(run_cli, write) -> None:
    write("callback.yaml", CONFIG)
    write(
        "suite/a.yaml", "id: same\nagent: restaurant-reservations\ncaller: {persona: p, goal: g}\n"
    )
    write(
        "suite/b.yaml", "id: same\nagent: restaurant-reservations\ncaller: {persona: p, goal: g}\n"
    )
    assert "duplicate scenario id 'same'" in run_cli("validate", "suite").stderr
    write(
        "suite/b.yaml",
        "id: b\nagent: restaurant-reservations\ntrails: 3\ncaller: {persona: p, goal: g}\n",
    )
    write("suite/c.yaml", "- not a mapping\n")
    done = run_cli("validate", "suite")
    assert done.returncode == 2 and "trails" in done.stderr and "c.yaml" in done.stderr


def test_unknown_agent_target_is_a_config_error(run_cli, write) -> None:
    write("ok.yaml", "id: x\nagent: nobody\ncaller: {persona: p, goal: g}\n")
    done = run_cli("validate", "ok.yaml")
    assert done.returncode == 2 and "nobody" in done.stderr


def test_invalid_config_names_the_field(run_cli, write) -> None:
    write("callback.yaml", "targets:\n  bot: {transport: carrier-pigeon}\n")
    write("ok.yaml", "id: x\nagent: bot\ncaller: {persona: p, goal: g}\n")
    done = run_cli("validate", "ok.yaml")
    assert done.returncode == 2 and "targets.bot" in done.stderr


@pytest.mark.parametrize(
    ("args", "message"),
    [(("validate",), "Missing"), (("nosuchcmd",), "No such command")],
)
def test_usage_errors_exit_2_with_a_message_not_a_traceback(run_cli, args, message) -> None:
    done = run_cli(*args)
    assert done.returncode == 2, done.stderr
    assert message in done.stderr and "Traceback" not in done.stderr


def test_unknown_baseline_is_an_error_before_any_call(run_cli, write) -> None:
    write("callback.yaml", CONFIG)
    write("scenarios/move.yaml", SPEC_EXAMPLE)
    done = run_cli("run", "scenarios", "--baseline", "nope")
    assert done.returncode == 2 and "no baseline 'nope'" in done.stderr


def test_misspelt_min_effect_is_an_error(run_cli, write) -> None:
    write("callback.yaml", CONFIG + "min_effect: {response_latency_p59_s: 0.1}\n")
    write("scenarios/move.yaml", SPEC_EXAMPLE)
    done = run_cli("run", "scenarios")
    assert done.returncode == 2 and "response_latency_p59_s" in done.stderr


def test_baseline_save_without_runs_is_an_error(run_cli) -> None:
    done = run_cli("baseline", "save", "main")
    assert done.returncode == 2 and "no runs" in done.stderr


def test_init_creates_a_project_that_validates(run_cli, tmp_path) -> None:
    done = run_cli("init")
    assert done.returncode == 0, done.stderr
    assert (tmp_path / "callback.yaml").is_file() and (
        tmp_path / "scenarios/example.yaml"
    ).is_file()
    assert run_cli("validate", "scenarios").returncode == 0

    again = run_cli("init")
    assert again.returncode == 2 and "already exists" in again.stderr
    assert run_cli("init", "--force").returncode == 0


def test_ci_latency_limit_is_announced_and_validated(run_cli, write, monkeypatch) -> None:
    write("callback.yaml", "targets:\n  a: {transport: websocket, url: 'ws://127.0.0.1:9'}\n")
    write("s.yaml", "id: s\nagent: a\ncaller: {persona: p, goal: g, script: [hi]}\n")
    monkeypatch.setenv("CALLBACK_CI_LATENCY_LIMIT_S", "2.0")
    done = run_cli("run", "s.yaml")
    assert "CI limit: reply delay p95 up to 2 s" in done.stdout, done.stdout
    assert "the real target is 1.5 s" in done.stdout

    monkeypatch.setenv("CALLBACK_CI_DRIFT_LIMIT_S", "1.0")
    both = run_cli("run", "s.yaml")
    assert "CI limit: chaos timing drift up to 1 s" in both.stdout, both.stdout
    assert "the real target is 0.1 s" in both.stdout
    monkeypatch.delenv("CALLBACK_CI_DRIFT_LIMIT_S")

    monkeypatch.setenv("CALLBACK_CI_YIELD_LIMIT_S", "1.1")
    yielding = run_cli("run", "s.yaml")
    assert "time to stop when interrupted (p95) up to 1.1 s" in yielding.stdout, yielding.stdout
    assert "the real target is 0.6 s" in yielding.stdout
    monkeypatch.delenv("CALLBACK_CI_YIELD_LIMIT_S")

    monkeypatch.setenv("CALLBACK_CI_LATENCY_LIMIT_S", "fast")
    bad = run_cli("run", "s.yaml")
    assert bad.returncode == 2 and "is not a number of seconds" in bad.stderr


def test_ci_yield_limit_leaves_talk_over_at_the_real_target(monkeypatch) -> None:
    from callback_voice.core.models.scenario import Scenario
    from callback_voice.core.runner.ci_limits import apply_ci_limits

    scenario = Scenario.model_validate(
        {"id": "s", "agent": "a", "caller": {"persona": "p", "goal": "g", "script": ["hi"]}}
    )
    monkeypatch.setenv("CALLBACK_CI_YIELD_LIMIT_S", "1.1")
    [loosened], [override] = apply_ci_limits([scenario])
    assert loosened.expect.thresholds.time_to_yield_p95_s == 1.1
    assert loosened.expect.thresholds.talk_over_grace_s == 0.6  # not stretched to 1.1
    assert (override.metric, override.target, override.applied) == ("time_to_yield_p95_s", 0.6, 1.1)


def _latency_run(passed: bool):
    from datetime import UTC, datetime

    from callback_voice.core.models.aggregate import Aggregate
    from callback_voice.core.models.run_result import RunResult
    from callback_voice.core.models.scenario_result import ScenarioResult

    latency = Aggregate(
        name="response_latency_p95_s",
        value=1.2 if passed else 4.1,
        ci_low=None,
        ci_high=None,
        n=3,
        unit="s",
        method="deterministic",
        threshold=1.5,
        passed=passed,
    )
    scenario = ScenarioResult(scenario_id="s", agent="a", passed=passed, aggregates=[latency])
    return RunResult(
        run_id="r",
        created_at=datetime.now(UTC),
        callback_version="test",
        agent_config_hash="h",
        mode="off",
        scenarios=[scenario],
        passed=passed,
        exit_code=0 if passed else 1,
    )


def test_reply_delay_failure_on_github_actions_names_the_runner_size() -> None:
    from callback_voice.cli.render.ci_runner_hint import ci_runner_hint

    failed, ok = _latency_run(passed=False), _latency_run(passed=True)
    hint = ci_runner_hint(failed, {"GITHUB_ACTIONS": "true"}, 2)
    assert hint is not None
    assert "GitHub Actions runner with 2 CPU cores (s)" in hint.plain
    assert "CALLBACK_CI_LATENCY_LIMIT_S" in hint.plain
    already = ci_runner_hint(
        failed, {"GITHUB_ACTIONS": "true", "CALLBACK_CI_LATENCY_LIMIT_S": "2.0"}, 4
    )
    assert already is not None and "is already 2.0 s" in already.plain
    assert ci_runner_hint(failed, {}, 2) is None  # not on GitHub Actions
    assert ci_runner_hint(ok, {"GITHUB_ACTIONS": "true"}, 2) is None  # nothing failed


def test_unchecked_plain_english_rules_are_announced_before_the_run() -> None:
    from callback_voice.cli.render.rules_notice import rules_notice
    from callback_voice.core.models.scenario import Scenario

    base = {"agent": "a", "caller": {"persona": "p", "goal": "g", "script": ["hi"]}}
    plain = Scenario.model_validate(
        {**base, "id": "plain", "expect": {"must_not": ["Promise a refund", {"says": "x"}]}}
    )
    pattern_only = Scenario.model_validate(
        {**base, "id": "pattern", "expect": {"must_not": [{"says": "x"}]}}
    )
    notice = rules_notice([plain, pattern_only], judge_configured=False)
    assert notice is not None and "1 plain-English must_not rule(s) in plain" in notice.plain
    assert rules_notice([plain], judge_configured=True) is None
    assert rules_notice([pattern_only], judge_configured=False) is None
