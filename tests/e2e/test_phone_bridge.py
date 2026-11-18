"""The phone bridge with any provider, and the whole chain:
Callback → phone network → bridge → agent. Each test runs with Twilio and an invented one."""

import asyncio
import contextlib
import socket
import time

import numpy as np
import pytest
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from callback_voice.phone_bridge.serve_phone_bridge import bridge_stream_url, serve_phone_bridge
from callback_voice.transports.phone_transport import PhoneTransport
from tests.e2e.phone_fakes import (
    WIRES,
    FakeAgent,
    FakeDialer,
    FakeNetwork,
    Wire,
    local,
    tone,
    until,
)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@contextlib.asynccontextmanager
async def bridge(wire: Wire, agent: FakeAgent, press_key_after_s: float | None = None):  # type: ignore[no-untyped-def]
    port = _free_port()
    ready = asyncio.Event()
    task = asyncio.create_task(
        serve_phone_bridge(
            wire.protocol, agent.url, "t0k", "127.0.0.1", port, ready, press_key_after_s
        )
    )
    await asyncio.wait_for(ready.wait(), 3)
    try:
        yield local(bridge_stream_url("https://example.app", "t0k"), port)
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


def _loud(messages: list[str | bytes], wire: Wire) -> bool:
    audio = [a for m in messages if (a := wire.audio_of(m)) is not None]
    return bool(audio) and float(np.abs(np.concatenate(audio)).max()) > 0.1


@pytest.mark.parametrize("wire", WIRES, ids=lambda w: w.protocol.name)
async def test_bridge_converts_both_ways(wire: Wire) -> None:
    async with (
        FakeAgent() as agent,
        bridge(wire, agent) as url,
        connect(url, max_queue=None) as phone,
    ):
        await phone.send(wire.start("MZ1", "CA9", {"callback_call_id": "call-7"}))
        await asyncio.wait_for(agent.connected.wait(), 3)
        assert agent.call_ids == ["call-7"]  # the caller's call id reaches the agent

        await phone.send(wire.media(tone(wire.protocol.sample_rate)))
        await phone.send(wire.dtmf("4"))
        await until(lambda: agent.heard and agent.control)
        assert np.abs(np.concatenate(agent.heard)).max() > 0.1  # PCM16 at 16 kHz
        assert agent.control[0] == {"type": "dtmf", "digits": "4"}

        received: list[str | bytes] = []
        with contextlib.suppress(TimeoutError):
            async with asyncio.timeout(1.0):
                while not _loud(received, wire):
                    received.append(await phone.recv())
        assert _loud(received, wire)  # the agent's greeting, in the provider's format

        await phone.send(wire.stop())
        await until(lambda: {"type": "hangup"} in agent.control)


@pytest.mark.parametrize("wire", WIRES, ids=lambda w: w.protocol.name)
async def test_the_agent_hanging_up_closes_the_stream(wire: Wire) -> None:
    async with (
        FakeAgent() as agent,
        bridge(wire, agent) as url,
        connect(url, max_queue=None) as phone,
    ):
        await phone.send(wire.start("MZ1", "CA9", {}))
        await asyncio.wait_for(agent.connected.wait(), 3)
        assert agent.call_ids == ["CA9"]  # no Callback call id: the provider's call ref
        agent.hang_up.set()
        with pytest.raises(ConnectionClosed):
            async with asyncio.timeout(3):
                while True:
                    await phone.recv()


async def test_a_stranger_without_the_token_is_turned_away() -> None:
    async with FakeAgent() as agent, bridge(WIRES[0], agent) as url:
        async with connect(url.replace("t0k", "guess"), max_queue=None) as phone:
            with pytest.raises(ConnectionClosed):
                await phone.recv()
            assert phone.close_code == 1008
        assert not agent.connected.is_set()


@pytest.mark.parametrize("wire", WIRES, ids=lambda w: w.protocol.name)
async def test_pressing_a_key_before_the_agent_joins(wire: Wire) -> None:
    async with (
        FakeAgent() as agent,
        bridge(wire, agent, press_key_after_s=0.3) as url,
        connect(url, max_queue=None) as phone,
    ):
        began = time.monotonic()
        await phone.send(wire.start("MZ1", "CA9", {}))
        await phone.send(wire.media(tone(wire.protocol.sample_rate)))  # the trial message
        key: list[str | bytes] = []
        async with asyncio.timeout(3):
            while not _loud(key, wire):
                key.append(await phone.recv())
        assert time.monotonic() - began >= 0.3  # the key comes after the wait
        assert not agent.connected.is_set()  # and the agent joins only after it
        await asyncio.wait_for(agent.connected.wait(), 3)
        assert agent.heard == []  # the message was not passed on


@pytest.mark.parametrize("wire", WIRES, ids=lambda w: w.protocol.name)
@pytest.mark.parametrize("delay_s", [0.0, 0.15])
async def test_whole_chain_callback_to_agent(wire: Wire, delay_s: float) -> None:
    """Callback dials, the network connects the number's stream to the bridge, the
    bridge calls the agent. Audio flows end to end; hanging up reaches the agent."""
    port = _free_port()
    async with FakeAgent() as agent, bridge(wire, agent) as number_url:
        dialer = FakeDialer(FakeNetwork(wire, port, number_url, delay_s=delay_s))
        transport = PhoneTransport(
            wire.protocol,
            dialer,
            to_number="+15550001111",
            from_number="+15550002222",
            public_url="https://example.app",
            listen_port=port,
            answer_timeout_s=3,
        )
        began = time.monotonic()
        await transport.connect("call-9")
        await until(lambda: agent.call_ids)
        assert agent.call_ids == ["CA1"]  # the far leg's provider ref; see docs/transports.md

        await until(lambda: transport.inbound.qsize() > 0)
        assert time.monotonic() - began >= delay_s  # the network delay is in the path
        heard = np.concatenate(transport.drain())
        assert np.abs(heard).max() > 0.1  # the agent's greeting, through two resamplings

        # Half a second of caller audio, sent in real time, reaches the agent about
        # delay_s later and still in real time: a delay must not slow the stream down.
        sent_at = time.monotonic()
        for _ in range(25):
            await transport.send_audio(tone(16_000, 0.02))
            await asyncio.sleep(0.02)
        await until(lambda: sum(len(a) for a in agent.heard) >= 0.45 * 16_000)
        assert time.monotonic() - sent_at < 0.5 + delay_s + 0.3

        await transport.hangup()
        await until(lambda: {"type": "hangup"} in agent.control)
        assert dialer.ended == ["CA1"]
