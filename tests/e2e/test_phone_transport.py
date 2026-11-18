"""The phone transport with any provider: each test runs with Twilio and an invented one."""

import asyncio
import contextlib
import socket

import numpy as np
import pytest
from websockets.asyncio.client import connect
from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from callback_voice.errors import TransportError
from callback_voice.transports.phone_transport import PhoneTransport
from tests.e2e.phone_fakes import WIRES, FakeDialer, FakeNetwork, Wire, tone, until


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class FarPhone:
    """Whatever answers the number: plays a tone, records what it hears, can hang up."""

    def __init__(self, wire: Wire) -> None:
        self.wire = wire
        self.heard: list[np.ndarray] = []
        self.hang_up = asyncio.Event()

    async def __aenter__(self) -> "FarPhone":
        self._server = await serve(self._handle, "127.0.0.1", 0)
        self.url = f"ws://127.0.0.1:{next(iter(self._server.sockets)).getsockname()[1]}/n"
        return self

    async def __aexit__(self, *exc: object) -> None:
        self._server.close()

    async def _handle(self, ws: ServerConnection) -> None:
        await ws.recv()  # the network's start message
        await ws.send(self.wire.media(tone(self.wire.protocol.sample_rate)))

        async def listen() -> None:
            with contextlib.suppress(ConnectionClosed):
                async for message in ws:
                    if (audio := self.wire.audio_of(message)) is not None:
                        self.heard.append(audio)

        listener = asyncio.create_task(listen())
        await asyncio.wait(
            [listener, asyncio.create_task(self.hang_up.wait())],
            return_when=asyncio.FIRST_COMPLETED,
        )
        listener.cancel()  # hanging up: the network sees this leg end and stops the call


def _transport(dialer: FakeDialer, port: int, timeout_s: float = 3.0) -> PhoneTransport:
    wire_protocol = dialer.network.wire.protocol if dialer.network else WIRES[0].protocol
    return PhoneTransport(
        wire_protocol,
        dialer,
        to_number="+15550001111",
        from_number="+15550002222",
        public_url="https://example.app",
        listen_port=port,
        answer_timeout_s=timeout_s,
    )


@pytest.mark.parametrize("wire", WIRES, ids=lambda w: w.protocol.name)
async def test_a_call_streams_both_ways_and_hangs_up(wire: Wire) -> None:
    port = _free_port()
    async with FarPhone(wire) as phone:
        dialer = FakeDialer(FakeNetwork(wire, port, phone.url))
        transport = _transport(dialer, port)
        await transport.connect("call-1")
        assert dialer.calls[0]["url"].startswith("wss://example.app/media/")
        assert dialer.calls[0]["call_id"] == "call-1"

        await until(lambda: transport.inbound.qsize() > 0)
        assert np.abs(np.concatenate(transport.drain())).max() > 0.1  # the far tone, at 16 kHz

        for _ in range(5):
            await transport.send_audio(tone(16_000, 0.02))
        await until(lambda: len(phone.heard) > 0)

        await transport.hangup()
        await transport.hangup()  # idempotent
        assert transport.close_reason == "caller_hangup"
        assert dialer.ended == ["CA1"] and dialer.closed

        # What the state webhook gets, so the agent's side can find this call.
        details = transport.call_details()
        assert details["provider"] == wire.protocol.name
        assert (details["from_number"], details["to_number"]) == ("+15550002222", "+15550001111")
        assert details["provider_call_ref"] == "CA1"
        assert float(details["call_placed_at"]) <= float(details["call_ended_at"])


@pytest.mark.parametrize("wire", WIRES, ids=lambda w: w.protocol.name)
async def test_the_far_end_hanging_up_ends_the_call(wire: Wire) -> None:
    port = _free_port()
    async with FarPhone(wire) as phone:
        transport = _transport(FakeDialer(FakeNetwork(wire, port, phone.url)), port)
        await transport.connect("call-2")
        phone.hang_up.set()
        await asyncio.wait_for(transport.closed.wait(), 3)
        assert transport.close_reason == "agent_hangup"
        await transport.hangup()


async def test_a_refused_call_explains_and_frees_the_port() -> None:
    port = _free_port()
    with pytest.raises(TransportError, match="unverified"):
        await _transport(FakeDialer(refuse="the number is unverified"), port).connect("c")
    with socket.socket() as s:
        s.bind(("127.0.0.1", port))  # the stream server is gone


async def test_an_unanswered_call_is_hung_up() -> None:
    port = _free_port()
    dialer = FakeDialer(FakeNetwork(WIRES[0], port, number_url=None))
    with pytest.raises(TransportError, match="did not answer"):
        await _transport(dialer, port, timeout_s=0.2).connect("c")
    assert dialer.ended == ["CA1"] and dialer.closed


async def test_a_stranger_without_the_token_is_turned_away() -> None:
    port = _free_port()
    dialer = FakeDialer(FakeNetwork(WIRES[0], port, number_url=None))
    connecting = asyncio.create_task(_transport(dialer, port, timeout_s=1.0).connect("c"))
    await until(lambda: dialer.calls)
    async with connect(f"ws://127.0.0.1:{port}/media/guess") as ws:
        with pytest.raises(ConnectionClosed):
            await ws.recv()
        assert ws.close_code == 1008
    with pytest.raises(TransportError):
        await connecting
