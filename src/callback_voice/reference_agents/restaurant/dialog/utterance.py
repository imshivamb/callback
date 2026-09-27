from dataclasses import dataclass

from callback_voice.reference_agents.restaurant.nlu.detect_intents import Intent, detect_intents
from callback_voice.reference_agents.restaurant.nlu.parse_day import parse_day
from callback_voice.reference_agents.restaurant.nlu.parse_party_size import parse_party_size
from callback_voice.reference_agents.restaurant.nlu.parse_time import TimeRequest, parse_time
from callback_voice.text.spoken_code import find_code


@dataclass(frozen=True, slots=True)
class Utterance:
    """Everything the agent understood from one caller turn."""

    text: str
    intents: frozenset[Intent]
    day: str | None
    time: TimeRequest | None
    party_size: int | None
    code: str | None

    def has(self, intent: Intent) -> bool:
        return intent in self.intents


def understand(text: str, *, expecting_time: bool = False) -> Utterance:
    return Utterance(
        text=text,
        intents=frozenset(detect_intents(text)),
        day=parse_day(text),
        time=parse_time(text, expecting_time=expecting_time),
        party_size=parse_party_size(text),
        code=find_code(text),
    )
