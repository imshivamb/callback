import asyncio
import json
from pathlib import Path
from typing import Any, Literal

from callback_voice.caller.brain.base import CallerBrain, CallerLine
from callback_voice.errors import ProviderError

type CassetteMode = Literal["record", "replay"]


class CassetteBrain:
    """Recorded mode: remembers every line a live brain said, and can replay them.

    Recording wraps the live brain and writes each line as it is decided, with how long
    it took (version 2). Replaying returns the same lines in order without calling any
    model, which is how CI runs at zero cost, and takes the same time over each: a
    live caller thinks for a second or two before answering, and a replayed one that
    answered instantly would cut into the agent's pauses. Replay assumes the agent behaves as it did when recorded; if the
    agent now needs more turns, the cassette runs out and the call errors with a
    hint to re-record.
    """

    def __init__(self, path: Path, mode: CassetteMode, live: CallerBrain | None = None) -> None:
        self._path = path
        self._mode = mode
        self._live = live
        self._lines: list[dict[str, Any]] = []
        self._next = 0
        if mode == "replay":
            if not path.is_file():
                raise ProviderError(
                    f"no recorded caller for this scenario and seed ({path.name})",
                    hint="run once with --record (needs the caller LLM) to create it",
                )
            recording = json.loads(path.read_text(encoding="utf-8"))
            self._lines = recording["lines"]
        self.needs_agent_text = mode == "record" and live is not None and live.needs_agent_text
        self.timing_missing = mode == "replay" and any("think_s" not in x for x in self._lines)
        self._ready_s: float | None = None

    async def next_line(self, agent_said: str) -> CallerLine | None:
        if self._mode == "replay":
            if self._next >= len(self._lines):
                raise ProviderError(
                    "the recorded caller ran out of lines: the agent's behaviour changed",
                    hint="re-record with --record",
                )
            line = self._lines[self._next]
            # Think as long as the recorded caller did, before committing to the line, so
            # the agent resuming meanwhile cancels the plan exactly as it did then.
            await asyncio.sleep(float(line.get("think_s", 0.0)))
            self._next += 1
            self._ready_s = line.get("ready_s")
            return CallerLine(line["text"], line["hang_up"], line["goal_reached"])
        assert self._live is not None
        result = await self._live.next_line(agent_said)
        self._lines.append(
            {
                "agent_said": agent_said,
                "text": result.text if result else "",
                "hang_up": result is None or result.hang_up,
                "goal_reached": bool(result and result.goal_reached),
            }
        )
        self._save()
        return result

    def note_interjection(self, text: str) -> None:
        if self._live is not None:
            self._live.note_interjection(text)

    def revise_last_line(self, text: str) -> None:
        if self._live is not None:
            self._live.revise_last_line(text)

    def apply_updates(self, updates: dict[str, Any]) -> None:
        if self._live is not None:
            self._live.apply_updates(updates)

    def note_timing(self, think_s: float, ready_s: float) -> None:
        if self._mode == "record" and self._lines:
            self._lines[-1]["think_s"] = round(think_s, 3)
            self._lines[-1]["ready_s"] = round(ready_s, 3)
            self._save()

    def replay_ready_s(self) -> float | None:
        return self._ready_s if self._mode == "replay" else None

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps({"version": 2, "lines": self._lines}, indent=2), encoding="utf-8"
        )
