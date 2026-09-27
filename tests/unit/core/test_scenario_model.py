from pathlib import Path

import pytest

from callback_voice.chaos.params.backchannel import BackchannelParams
from callback_voice.chaos.params.barge_in import BargeInParams
from callback_voice.core.scenarios.load_scenario import load_scenario
from callback_voice.core.scenarios.load_suite import load_suite
from callback_voice.errors import ScenarioError

SPEC_EXAMPLE = """
id: move-dinner-booking-hinglish-noisy
agent: restaurant-reservations
trials: 5
max_duration_s: 180
caller:
  persona: "Priya, 34, calling from a busy street, in a hurry"
  goal: "Move Friday 8pm table for 4 to Saturday, any time 7-9pm, window seat if possible"
  knows: {name: Priya Sharma, phone: "98100 12345", booking_ref: "DX7Q2", party_size: 4}
  language: hi-en
  voice: female_in_1
  patience: low
  speaking_rate: 1.15
chaos:
  noise: {bed: street, snr_db: 10}
  events:
    - barge_in: {on: agent_turn, turn: 2, after_s: 0.8, say: "haan haan, Saturday"}
    - backchannel: {on: agent_turn, every: 1, say: ["hmm", "okay"]}
    - change_mind: {on: caller_turn, turn: 4, say: "actually make it 5 people"}
    - silence: {on: caller_turn, turn: 3, duration_s: 6}
    - packet_loss: {pct: 3, from_s: 30, to_s: 60}
expect:
  state: {webhook: "http://localhost:8080/verify", match: {status: moved, day: saturday, party_size: 5, hour_between: [19, 21]}}
  entities_spoken: ["DX7Q2"]
  must_not: ["reveal other guests' bookings", "confirm a slot that is full"]
  thresholds: {response_latency_p95_s: 1.5, time_to_yield_p95_s: 0.6, task_success_rate: 0.8}
"""


def test_spec_example_parses(write_yaml) -> None:
    scenario = load_scenario(write_yaml("s.yaml", SPEC_EXAMPLE))
    assert scenario.trials == 5
    assert scenario.caller.failed_attempts_allowed == 2
    barge, backchannel, *_ = scenario.chaos.events
    assert isinstance(barge.params, BargeInParams) and barge.after_s == 0.8
    assert barge.trigger is not None and barge.trigger.matches_turn(2)
    assert isinstance(backchannel.params, BackchannelParams)
    assert backchannel.params.say == ("hmm", "okay")
    assert backchannel.after_s == 1.2  # type default
    assert [e.id for e in scenario.chaos.events][:2] == ["barge_in-1", "backchannel-2"]
    assert scenario.expect.thresholds.talk_over_ratio == 0.05  # spec default kept


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
        ("- dtmf: {on: time, at_s: 3, digits: '12x'}", "digits"),
    ],
)
def test_bad_events_are_reported_with_location(write_yaml, event: str, message: str) -> None:
    body = f"id: x\nagent: a\ncaller: {{persona: p, goal: g}}\nchaos:\n  events:\n    {event}\n"
    with pytest.raises(ScenarioError) as info:
        load_scenario(write_yaml("bad.yaml", body))
    assert message in str(info.value)
    assert "bad.yaml" in str(info.value)


def test_unknown_top_level_key_is_rejected(write_yaml) -> None:
    with pytest.raises(ScenarioError, match="trails"):
        load_scenario(
            write_yaml("t.yaml", "id: x\nagent: a\ntrails: 3\ncaller: {persona: p, goal: g}\n")
        )


def test_suite_reports_every_bad_file_and_duplicate_ids(tmp_path: Path, write_yaml) -> None:
    write_yaml("suite/a.yaml", "id: same\nagent: a\ncaller: {persona: p, goal: g}\n")
    write_yaml("suite/b.yaml", "id: same\nagent: a\ncaller: {persona: p, goal: g}\n")
    with pytest.raises(ScenarioError, match="duplicate scenario id 'same'"):
        load_suite(tmp_path / "suite")
    write_yaml("suite/b.yaml", "id: other\nagent: a\n")
    write_yaml("suite/c.yaml", "- not a mapping\n")
    with pytest.raises(ScenarioError) as info:
        load_suite(tmp_path / "suite")
    assert "b.yaml" in str(info.value) and "c.yaml" in str(info.value)
