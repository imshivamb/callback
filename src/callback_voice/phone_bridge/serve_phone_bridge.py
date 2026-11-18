import asyncio
import contextlib
import json
import logging

from websockets.asyncio.client import ClientConnection, connect
from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed, WebSocketException

from callback_voice.audio.dtmf import dtmf_tones
from callback_voice.audio.format import SAMPLE_RATE, Audio
from callback_voice.audio.pcm import from_pcm16, to_pcm16
from callback_voice.audio.stream_resampler import StreamResampler
from callback_voice.telephony.media_stream import MediaStreamProtocol, StreamEvent

log = logging.getLogger("callback.phone_bridge")
CALL_ID_HEADER = "X-Callback-Call-Id"
STREAM_PATH = "/stream/"


def bridge_stream_url(public_url: str, token: str) -> str:
    """The address a provider's number streams its calls to."""
    host = public_url.removeprefix("https://").removeprefix("wss://").rstrip("/")
    return f"wss://{host}{STREAM_PATH}{token}"


async def serve_phone_bridge(
    protocol: MediaStreamProtocol,
    agent_url: str,
    token: str,
    host: str = "127.0.0.1",
    port: int = 8767,
    ready: asyncio.Event | None = None,
    press_key_after_s: float | None = None,
) -> None:
    """Put a WebSocket agent behind a phone number, until cancelled.

    Each call to the number streams here in the provider's format (``protocol``).
    The bridge opens one WebSocket to ``agent_url`` per call and converts both ways to
    the raw PCM16 protocol in docs/transports.md, at 16 kHz. The agent hanging up
    closes the stream, which ends the call; the caller hanging up sends the agent
    ``{"type": "hangup"}``.

    ``press_key_after_s``: some accounts (a Twilio trial) play a message on each call
    and wait for a key press. With this set, the bridge drops audio for that long,
    presses 1 as a tone, and only then connects the agent, so the agent does not hear
    the message.
    """

    async def handle(phone: ServerConnection) -> None:
        if not phone.request or not phone.request.path.rstrip("/").endswith(
            f"{STREAM_PATH}{token}"
        ):
            await phone.close(1008, "unknown stream")
            return
        start = await _wait_for_start(phone, protocol)
        if start is None:
            return
        stream_id = start.stream_id or ""
        call_id = start.parameters.get("callback_call_id") or start.call_ref or stream_id
        log.info("call %s: stream %s started", call_id, stream_id)
        if press_key_after_s is not None:
            await _press_key(phone, protocol, stream_id, press_key_after_s)
        try:
            agent = await connect(
                agent_url,
                additional_headers={CALL_ID_HEADER: call_id},
                max_size=2**22,
                ping_interval=None,
                open_timeout=10,
            )
        except (OSError, TimeoutError, WebSocketException) as exc:
            log.error("call %s: cannot reach the agent at %s: %s", call_id, agent_url, exc)
            await phone.close(1011, "agent unreachable")
            return
        async with agent:
            await _relay(phone, agent, protocol, stream_id)
        log.info("call %s ended", call_id)

    async with serve(handle, host, port, ping_interval=None, max_size=2**20):
        log.info("phone bridge (%s) on ws://%s:%d → %s", protocol.name, host, port, agent_url)
        if ready is not None:
            ready.set()
        await asyncio.Future()


async def _wait_for_start(
    phone: ServerConnection, protocol: MediaStreamProtocol
) -> StreamEvent | None:
    try:
        async for message in phone:
            event = protocol.parse(message)
            if event.kind == "start":
                return event
            if event.kind == "stop":
                return None
    except ConnectionClosed:
        pass
    return None


async def _press_key(
    phone: ServerConnection, protocol: MediaStreamProtocol, stream_id: str, after_s: float
) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + after_s
    with contextlib.suppress(TimeoutError, ConnectionClosed):
        while (left := deadline - loop.time()) > 0:
            await asyncio.wait_for(phone.recv(), left)  # drop the message's audio
    tone = StreamResampler(SAMPLE_RATE, protocol.sample_rate).process(dtmf_tones("1", tone_s=0.3))
    await _send_paced(phone, protocol, stream_id, tone)
    await asyncio.sleep(1.0)


async def _send_paced(
    phone: ServerConnection, protocol: MediaStreamProtocol, stream_id: str, audio: Audio
) -> None:
    frame = protocol.sample_rate // 50  # 20 ms
    for i in range(0, len(audio), frame):
        with contextlib.suppress(ConnectionClosed):
            await phone.send(protocol.media(stream_id, audio[i : i + frame]))
        await asyncio.sleep(0.02)


async def _relay(
    phone: ServerConnection,
    agent: ClientConnection,
    protocol: MediaStreamProtocol,
    stream_id: str,
) -> None:
    to_agent = StreamResampler(protocol.sample_rate, SAMPLE_RATE)
    to_phone = StreamResampler(SAMPLE_RATE, protocol.sample_rate)

    async def phone_to_agent() -> None:
        with contextlib.suppress(ConnectionClosed):
            async for message in phone:
                event = protocol.parse(message)
                if event.kind == "media" and event.audio is not None:
                    await agent.send(to_pcm16(to_agent.process(event.audio)))
                elif event.kind == "dtmf" and event.digits:
                    await agent.send(json.dumps({"type": "dtmf", "digits": event.digits}))
                elif event.kind == "stop":
                    break
        with contextlib.suppress(ConnectionClosed):
            await agent.send(json.dumps({"type": "hangup"}))

    async def agent_to_phone() -> None:
        with contextlib.suppress(ConnectionClosed):
            async for message in agent:
                if isinstance(message, bytes):
                    audio = to_phone.process(from_pcm16(message))
                    await phone.send(protocol.media(stream_id, audio))
        with contextlib.suppress(ConnectionClosed):
            await phone.close(1000, "agent hung up")  # closing the stream ends the call

    tasks = [asyncio.create_task(phone_to_agent()), asyncio.create_task(agent_to_phone())]
    _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
