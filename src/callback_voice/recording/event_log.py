import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from callback_voice.core.models.call_event import CallEvent, EventKind

_EVENTS = TypeAdapter(list[CallEvent])


class EventLog:
    """Ordered events of one call; the scorer reads it alongside the recording."""

    def __init__(self) -> None:
        self.events: list[CallEvent] = []

    def add(self, t_s: float, kind: EventKind, **fields: Any) -> CallEvent:
        event = CallEvent(t_s=round(t_s, 4), kind=kind, **fields)
        self.events.append(event)
        return event

    def of_kind(self, kind: EventKind) -> list[CallEvent]:
        return [e for e in self.events if e.kind == kind]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as out:
            for event in sorted(self.events, key=lambda e: e.t_s):
                out.write(event.model_dump_json(exclude_defaults=True) + "\n")

    @staticmethod
    def load(path: Path) -> list[CallEvent]:
        lines = path.read_text(encoding="utf-8").splitlines()
        return _EVENTS.validate_python([json.loads(line) for line in lines if line.strip()])
