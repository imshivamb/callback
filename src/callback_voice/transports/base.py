import asyncio
from abc import ABC, abstractmethod

from callback_voice.audio.format import Audio


class Transport(ABC):
    """A live call to the agent under test.

    Adapters convert between the wire format (PCM16, mu-law, WebRTC, any sample
    rate) and Callback's internal 16 kHz float audio, so the caller engine never
    sees wire details. Inbound audio is queued as it arrives and drained by the
    engine's clock.
    """

    name: str

    def __init__(self) -> None:
        self.inbound: asyncio.Queue[Audio] = asyncio.Queue()
        self.closed = asyncio.Event()
        self.close_reason: str | None = None

    @abstractmethod
    async def connect(self, call_id: str) -> None:
        """Dial or join; returns once audio can flow."""

    @abstractmethod
    async def send_audio(self, audio: Audio) -> None:
        """Send one 20 ms frame of caller audio."""

    async def send_dtmf(self, digits: str) -> bool:
        """Send keypad digits out of band. Returns False when the transport has no DTMF
        channel, in which case the caller plays in-band tones instead."""
        return False

    @abstractmethod
    async def hangup(self) -> None:
        """End the call from the caller's side. Idempotent."""

    def drain(self) -> list[Audio]:
        """All inbound audio received since the last drain."""
        chunks: list[Audio] = []
        while not self.inbound.empty():
            chunks.append(self.inbound.get_nowait())
        return chunks

    def mark_closed(self, reason: str) -> None:
        if not self.closed.is_set():
            self.close_reason = reason
            self.closed.set()
