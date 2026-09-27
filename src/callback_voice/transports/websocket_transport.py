import asyncio
import contextlib
import json
import os

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, InvalidURI, WebSocketException

from callback_voice.audio.format import SAMPLE_RATE, Audio
from callback_voice.audio.pcm import from_pcm16, to_pcm16
from callback_voice.audio.stream_resampler import StreamResampler
from callback_voice.core.config.target_config import WebSocketTarget
from callback_voice.errors import TransportError
from callback_voice.transports.base import Transport

CALL_ID_HEADER = "X-Callback-Call-Id"


class WebSocketTransport(Transport):
    """Raw PCM16 mono over a WebSocket (docs/transports.md).

    Binary messages carry audio both ways. Text messages carry JSON control:
    Callback sends ``{"type": "hangup"}`` and ``{"type": "dtmf", "digits": "1"}``.
    The call id travels in the ``X-Callback-Call-Id`` header so an agent can tie
    its end state to the call for verification.
    """

    name = "websocket"

    def __init__(self, target: WebSocketTarget) -> None:
        super().__init__()
        self._target = target
        self._ws: ClientConnection | None = None
        self._reader: asyncio.Task[None] | None = None
        self._to_wire = StreamResampler(SAMPLE_RATE, target.sample_rate)
        self._from_wire = StreamResampler(target.sample_rate, SAMPLE_RATE)

    async def connect(self, call_id: str) -> None:
        headers = {CALL_ID_HEADER: call_id}
        for header, env in self._target.headers_env.items():
            if value := os.environ.get(env):
                headers[header] = value
        try:
            self._ws = await asyncio.wait_for(
                connect(
                    self._target.url,
                    additional_headers=headers,
                    max_size=2**22,
                    ping_interval=None,
                    open_timeout=10,
                ),
                timeout=12,
            )
        except (OSError, TimeoutError, InvalidURI, WebSocketException) as exc:
            raise TransportError(
                f"cannot connect to {self._target.url}: {exc or type(exc).__name__}",
                hint="is the agent running? `callback doctor` checks every target",
            ) from exc
        self._reader = asyncio.create_task(self._read())

    async def send_audio(self, audio: Audio) -> None:
        if self._ws is None or self.closed.is_set():
            return
        wire = self._to_wire.process(audio)
        with contextlib.suppress(ConnectionClosed):
            await self._ws.send(to_pcm16(wire))

    async def send_dtmf(self, digits: str) -> bool:
        if self._ws is None or self.closed.is_set():
            return False
        with contextlib.suppress(ConnectionClosed):
            await self._ws.send(json.dumps({"type": "dtmf", "digits": digits}))
        return False  # also play tones in-band: most WS agents only hear audio

    async def hangup(self) -> None:
        if self._ws is not None and not self.closed.is_set():
            with contextlib.suppress(ConnectionClosed):
                await self._ws.send(json.dumps({"type": "hangup"}))
                await self._ws.close(1000, "caller hung up")
        self.mark_closed("caller_hangup")
        if self._reader is not None:
            self._reader.cancel()

    async def _read(self) -> None:
        assert self._ws is not None
        try:
            async for message in self._ws:
                if isinstance(message, bytes):
                    audio = from_pcm16(message)
                    self.inbound.put_nowait(self._from_wire.process(audio))
            self.mark_closed("agent_hangup")
        except ConnectionClosed as closed:
            normal = closed.rcvd is not None and closed.rcvd.code in (1000, 1001)
            self.mark_closed("agent_hangup" if normal else f"connection_lost ({closed})")
