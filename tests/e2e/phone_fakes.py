"""Fakes for phone tests: provider wire formats, a fake dialer, a phone network and an agent.

Two providers on purpose: Twilio, and an invented one with another message shape and
codec, so every test shows the shared code is provider-neutral.
"""

import asyncio
import base64
import contextlib
import json
from abc import ABC, abstractmethod
from typing import Any

import numpy as np
from websockets.asyncio.client import ClientConnection, connect
from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from callback_voice.audio.format import Audio
from callback_voice.audio.mulaw import mulaw_decode, mulaw_encode
from callback_voice.audio.pcm import from_pcm16, to_pcm16
from callback_voice.telephony.dialer import PhoneDialer
from callback_voice.telephony.media_stream import MediaStreamProtocol, StreamEvent
from callback_voice.telephony.twilio import TwilioMediaStream


class OtherMediaStream(MediaStreamProtocol):
    """An invented provider: {"type": ...} messages, base64 PCM16 at 16 kHz."""

    name = "other"
    sample_rate = 16_000

    def parse(self, message: str | bytes) -> StreamEvent:
        event = json.loads(message)
        kind = event.get("type")
        if kind == "hello":
            return StreamEvent(
                "start",
                stream_id=event["session"],
                call_ref=event["call"],
                parameters=event.get("vars", {}),
            )
        if kind == "audio":
            return StreamEvent("media", audio=from_pcm16(base64.b64decode(event["pcm"])))
        if kind == "key":
            return StreamEvent("dtmf", digits=event["key"])
        if kind == "bye":
            return StreamEvent("stop")
        return StreamEvent("other")

    def media(self, stream_id: str, audio: Audio) -> str:
        return json.dumps(
            {
                "type": "audio",
                "session": stream_id,
                "pcm": base64.b64encode(to_pcm16(audio)).decode(),
            }
        )


class Wire(ABC):
    """The provider's side of a stream: what its network sends, and reading what it gets."""

    protocol: MediaStreamProtocol

    @abstractmethod
    def start(self, stream_id: str, call_ref: str, params: dict[str, str]) -> str: ...
    @abstractmethod
    def media(self, audio: Audio) -> str: ...
    @abstractmethod
    def dtmf(self, digit: str) -> str: ...
    @abstractmethod
    def stop(self) -> str: ...
    @abstractmethod
    def audio_of(self, message: str | bytes) -> Audio | None: ...


class TwilioWire(Wire):
    protocol = TwilioMediaStream()

    def start(self, stream_id: str, call_ref: str, params: dict[str, str]) -> str:
        return json.dumps(
            {
                "event": "start",
                "start": {"streamSid": stream_id, "callSid": call_ref, "customParameters": params},
            }
        )

    def media(self, audio: Audio) -> str:
        payload = base64.b64encode(mulaw_encode(audio)).decode()
        return json.dumps({"event": "media", "media": {"track": "inbound", "payload": payload}})

    def dtmf(self, digit: str) -> str:
        return json.dumps({"event": "dtmf", "dtmf": {"digit": digit}})

    def stop(self) -> str:
        return json.dumps({"event": "stop"})

    def audio_of(self, message: str | bytes) -> Audio | None:
        event = json.loads(message)
        if event.get("event") != "media":
            return None
        return mulaw_decode(base64.b64decode(event["media"]["payload"]))


class OtherWire(Wire):
    protocol = OtherMediaStream()

    def start(self, stream_id: str, call_ref: str, params: dict[str, str]) -> str:
        return json.dumps({"type": "hello", "session": stream_id, "call": call_ref, "vars": params})

    def media(self, audio: Audio) -> str:
        return json.dumps({"type": "audio", "pcm": base64.b64encode(to_pcm16(audio)).decode()})

    def dtmf(self, digit: str) -> str:
        return json.dumps({"type": "key", "key": digit})

    def stop(self) -> str:
        return json.dumps({"type": "bye"})

    def audio_of(self, message: str | bytes) -> Audio | None:
        event = json.loads(message)
        return from_pcm16(base64.b64decode(event["pcm"])) if event.get("type") == "audio" else None


WIRES = [TwilioWire(), OtherWire()]


def tone(rate: int, seconds: float = 0.1, hz: float = 440.0) -> Audio:
    return (0.3 * np.sin(2 * np.pi * hz * np.arange(int(rate * seconds)) / rate)).astype(np.float32)


def local(stream_url: str, port: int) -> str:
    """A provider-facing wss:// URL, reached on this machine."""
    return f"ws://127.0.0.1:{port}/" + stream_url.split("/", 3)[3]


class FakeNetwork:
    """A phone network: a call from Callback lands on a number streamed to ``number_url``,
    or nowhere (``answer=False``). It relays audio between the two streams, with an
    optional one-way delay, like a provider connecting two calls."""

    def __init__(
        self, wire: Wire, callback_port: int, number_url: str | None, delay_s: float = 0.0
    ) -> None:
        self.wire = wire
        self.callback_port = callback_port
        self.number_url = number_url
        self.delay_s = delay_s
        self.task: asyncio.Task[None] | None = None
        self.hung_up = asyncio.Event()

    def place(self, stream_url: str, call_id: str) -> None:
        if self.number_url is not None:
            self.task = asyncio.create_task(
                self._call(local(stream_url, self.callback_port), call_id)
            )

    async def _call(self, callback_url: str, call_id: str) -> None:
        async with connect(self.number_url) as far, connect(callback_url) as near:  # type: ignore[arg-type]
            await far.send(self.wire.start("MZ-far", "CA1", {}))
            await near.send(self.wire.start("MZ-near", "CA1", {"callback_call_id": call_id}))
            legs = [
                asyncio.create_task(self._pipe(near, far)),
                asyncio.create_task(self._pipe(far, near)),
                asyncio.create_task(self.hung_up.wait()),
            ]
            await asyncio.wait(legs, return_when=asyncio.FIRST_COMPLETED)
            for leg in legs:
                leg.cancel()
            for ws in (far, near):
                with contextlib.suppress(ConnectionClosed):
                    await ws.send(self.wire.stop())
                    await ws.close()

    async def _pipe(self, source: ClientConnection, sink: ClientConnection) -> None:
        """Relay audio with ``delay_s`` of latency but no loss of rate: each frame is
        sent ``delay_s`` after it arrived (sleeping before each frame would slow the
        stream down instead of delaying it)."""
        loop = asyncio.get_running_loop()
        line: asyncio.Queue[tuple[float, str | bytes]] = asyncio.Queue()

        async def send_when_due() -> None:
            with contextlib.suppress(ConnectionClosed):
                while True:
                    due, message = await line.get()
                    if (wait := due - loop.time()) > 0:
                        await asyncio.sleep(wait)
                    await sink.send(message)

        sender = asyncio.create_task(send_when_due())
        try:
            with contextlib.suppress(ConnectionClosed):
                async for message in source:
                    audio = self.wire.audio_of(message)
                    if audio is not None:
                        line.put_nowait((loop.time() + self.delay_s, self.wire.media(audio)))
        finally:
            sender.cancel()


class FakeDialer(PhoneDialer):
    name = "fake"

    def __init__(self, network: FakeNetwork | None = None, *, refuse: str | None = None) -> None:
        self.network = network
        self.refuse = refuse
        self.calls: list[dict[str, str]] = []
        self.ended: list[str] = []
        self.closed = False

    def check_credentials(self) -> None:
        pass

    async def place_call(
        self, to_number: str, from_number: str, stream_url: str, call_id: str
    ) -> str:
        from callback_voice.errors import TransportError

        if self.refuse:
            raise TransportError(self.refuse)
        self.calls.append(
            {"to": to_number, "from": from_number, "url": stream_url, "call_id": call_id}
        )
        if self.network is not None:
            self.network.place(stream_url, call_id)
        return "CA1"

    async def end_call(self, call_ref: str) -> None:
        self.ended.append(call_ref)
        if self.network is not None:
            self.network.hung_up.set()

    async def close(self) -> None:
        self.closed = True


class FakeAgent:
    """A raw PCM16 WebSocket agent: plays a tone when called, records what it hears."""

    def __init__(self) -> None:
        self.heard: list[Audio] = []
        self.control: list[dict[str, Any]] = []
        self.call_ids: list[str] = []
        self.connected = asyncio.Event()
        self.hang_up = asyncio.Event()
        self.port = 0

    async def __aenter__(self) -> "FakeAgent":
        self._server = await serve(self._handle, "127.0.0.1", 0)
        self.port = next(iter(self._server.sockets)).getsockname()[1]
        return self

    async def __aexit__(self, *exc: object) -> None:
        self._server.close()

    @property
    def url(self) -> str:
        return f"ws://127.0.0.1:{self.port}"

    async def _handle(self, ws: ServerConnection) -> None:
        self.call_ids.append(ws.request.headers.get("X-Callback-Call-Id", "") if ws.request else "")
        self.connected.set()
        greeting = tone(16_000, 0.2, 600.0)
        for i in range(0, len(greeting), 320):
            await ws.send(to_pcm16(greeting[i : i + 320]))
            await asyncio.sleep(0.02)

        async def listen() -> None:
            with contextlib.suppress(ConnectionClosed):
                async for message in ws:
                    if isinstance(message, bytes):
                        self.heard.append(from_pcm16(message))
                    else:
                        self.control.append(json.loads(message))

        listener = asyncio.create_task(listen())
        await asyncio.wait(
            [listener, asyncio.create_task(self.hang_up.wait())],
            return_when=asyncio.FIRST_COMPLETED,
        )
        if self.hang_up.is_set():
            await ws.close(1000, "agent hung up")
        listener.cancel()


async def until(condition: Any, within_s: float = 3.0) -> None:
    """Wait for ``condition()`` to be true."""
    async with asyncio.timeout(within_s):
        while not condition():  # noqa: ASYNC110 - polling state the fakes expose
            await asyncio.sleep(0.01)
