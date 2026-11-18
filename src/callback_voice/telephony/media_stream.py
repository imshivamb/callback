from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

from callback_voice.audio.format import Audio

type StreamEventKind = Literal["start", "media", "dtmf", "stop", "other"]


@dataclass(frozen=True, slots=True)
class StreamEvent:
    """One message from a phone provider's media stream, in provider-neutral terms.

    ``audio`` is decoded float audio at the protocol's ``sample_rate``.
    """

    kind: StreamEventKind
    audio: Audio | None = None
    digits: str = ""
    stream_id: str | None = None
    call_ref: str | None = None
    parameters: dict[str, str] = field(default_factory=dict)


class MediaStreamProtocol(ABC):
    """A phone provider's media-stream wire format (Twilio Media Streams, and others).

    Providers stream call audio over a WebSocket with their own message shapes and
    codecs. An implementation turns their messages into ``StreamEvent`` and Callback's
    audio into their outbound message; everything else (relaying, resampling, pacing,
    hanging up) is shared.
    """

    name: str
    sample_rate: int

    @abstractmethod
    def parse(self, message: str | bytes) -> StreamEvent:
        """Read one inbound message."""

    @abstractmethod
    def media(self, stream_id: str, audio: Audio) -> str | bytes:
        """One outbound message carrying ``audio`` (at ``sample_rate``) into the call."""
