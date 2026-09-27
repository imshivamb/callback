from dataclasses import dataclass, field
from typing import Protocol

from callback_voice.audio.format import Audio


@dataclass(frozen=True, slots=True)
class Word:
    text: str
    start_s: float
    end_s: float


@dataclass(frozen=True, slots=True)
class Transcript:
    text: str
    language: str | None = None
    words: tuple[Word, ...] = field(default=())


class SpeechToText(Protocol):
    """Transcribes a complete utterance (16 kHz mono float)."""

    name: str

    async def transcribe(self, audio: Audio, *, language: str | None = None) -> Transcript: ...
