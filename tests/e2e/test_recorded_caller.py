"""A recorded AI caller replays its lines with the timing it had when recorded."""

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from callback_voice.caller.brain.base import CallerLine
from callback_voice.caller.brain.cassette_brain import CassetteBrain


class SlowLiveCaller:
    """Stands in for the LLM caller: answers after a fixed think time."""

    needs_agent_text = True
    timing_missing = False

    def __init__(self, think_s: float) -> None:
        self._think_s = think_s

    async def next_line(self, agent_said: str) -> CallerLine | None:
        await asyncio.sleep(self._think_s)
        return CallerLine(f"reply to {agent_said}")

    def note_interjection(self, text: str) -> None: ...
    def revise_last_line(self, text: str) -> None: ...
    def apply_updates(self, updates: dict[str, Any]) -> None: ...
    def note_timing(self, think_s: float, ready_s: float) -> None: ...
    def replay_ready_s(self) -> float | None:
        return None


async def test_replay_takes_as_long_as_the_recorded_caller(tmp_path: Path) -> None:
    path = tmp_path / "seed-1-abc.json"
    recorder = CassetteBrain(path, "record", SlowLiveCaller(0.3))
    began = time.monotonic()
    await recorder.next_line("hello")
    think_s = time.monotonic() - began
    recorder.note_timing(think_s, think_s + 0.2)  # rendering the voice took 0.2 s more
    saved = json.loads(path.read_text())
    assert saved["version"] == 2
    assert saved["lines"][0]["think_s"] >= 0.3
    assert saved["lines"][0]["ready_s"] >= 0.5

    replayer = CassetteBrain(path, "replay")
    assert replayer.timing_missing is False
    began = time.monotonic()
    line = await replayer.next_line("")
    assert line is not None and line.text == "reply to hello"
    assert time.monotonic() - began >= 0.3  # thought as long as it did live
    assert replayer.replay_ready_s() == saved["lines"][0]["ready_s"]


async def test_old_recordings_without_timing_are_flagged(tmp_path: Path) -> None:
    path = tmp_path / "seed-1-abc.json"
    line = {"agent_said": "", "text": "hi", "hang_up": False, "goal_reached": False}
    path.write_text(json.dumps({"version": 1, "lines": [line]}))
    replayer = CassetteBrain(path, "replay")
    assert replayer.timing_missing is True
    began = time.monotonic()
    assert (await replayer.next_line("")) is not None
    assert time.monotonic() - began < 0.1  # nothing to wait for
    assert replayer.replay_ready_s() is None
