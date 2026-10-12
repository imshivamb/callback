"""The Twilio transport against a fake Twilio: the REST API and the phone end of the stream."""

import asyncio
import base64
import contextlib
import json
import re
import socket
from urllib.parse import parse_qs

import httpx
import numpy as np
import pytest
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from callback_voice.audio.mulaw import mulaw_decode, mulaw_encode
from callback_voice.core.config.target_config import TwilioTarget
from callback_voice.errors import TransportError
from callback_voice.transports.twilio_transport import TwilioTransport

FRAME_8K = 160  # 20 ms of 8 kHz mu-law


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class FakeTwilio:
    """Answers the REST calls and plays the callee: streams a tone, records what it hears."""

    def __init__(self, port: int, *, answer: bool = True, status: int = 201) -> None:
        self.port = port
        self.answer = answer
        self.status = status
        self.requests: list[tuple[str, dict[str, list[str]]]] = []
        self.heard: list[dict[str, object]] = []
        self.phone: asyncio.Task[None] | None = None
        self.hang_up = asyncio.Event()

    def handler(self, request: httpx.Request) -> httpx.Response:
        form = parse_qs(request.content.decode())
        self.requests.append((request.url.path, form))
        if request.url.path.endswith("/Calls.json"):
            if self.status >= 400:
                return httpx.Response(self.status, json={"message": "The number is unverified"})
            if self.answer:
                url = re.search(r'Stream url="([^"]+)"', form["Twiml"][0])
                assert url is not None
                path = url.group(1).split("/", 3)[3]
                self.phone = asyncio.create_task(self._phone(f"ws://127.0.0.1:{self.port}/{path}"))
            return httpx.Response(201, json={"sid": "CA123"})
        return httpx.Response(200, json={"sid": "CA123", "status": "completed"})

    async def _phone(self, url: str) -> None:
        async with connect(url) as ws:
            await ws.send(json.dumps({"event": "connected"}))
            await ws.send(json.dumps({"event": "start", "start": {"streamSid": "MZ1"}}))
            tone = (0.3 * np.sin(2 * np.pi * 440 * np.arange(FRAME_8K * 5) / 8000)).astype(
                np.float32
            )
            payload = base64.b64encode(mulaw_encode(tone)).decode()
            await ws.send(
                json.dumps({"event": "media", "media": {"track": "inbound", "payload": payload}})
            )
            reader = asyncio.create_task(self._listen(ws))
            await self.hang_up.wait()
            with contextlib.suppress(ConnectionClosed):  # Callback may have hung up first
                await ws.send(json.dumps({"event": "stop"}))
            reader.cancel()

    async def _listen(self, ws: object) -> None:
        try:
            async for message in ws:  # type: ignore[attr-defined]
                self.heard.append(json.loads(message))
        except ConnectionClosed:
            pass


def _target(port: int) -> TwilioTarget:
    return TwilioTarget(
        to_number="+15550001111",
        from_number="+15550002222",
        public_url="https://example.ngrok.app",
        listen_port=port,
    )


@pytest.fixture(autouse=True)
def credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC_test")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "secret")


def _transport(fake: FakeTwilio, **kwargs: float) -> TwilioTransport:
    http = httpx.AsyncClient(transport=httpx.MockTransport(fake.handler))
    return TwilioTransport(_target(fake.port), http=http, **kwargs)


async def test_a_call_streams_both_ways_and_hangs_up() -> None:
    fake = FakeTwilio(_free_port())
    transport = _transport(fake)
    await transport.connect("call-1")

    path, form = fake.requests[0]
    assert path == "/2010-04-01/Accounts/AC_test/Calls.json"
    assert form["To"] == ["+15550001111"] and form["From"] == ["+15550002222"]
    assert 'Stream url="wss://example.ngrok.app/media/' in form["Twiml"][0]
    assert 'value="call-1"' in form["Twiml"][0]

    for _ in range(50):
        if transport.inbound.qsize():
            break
        await asyncio.sleep(0.01)
    heard = np.concatenate(transport.drain())
    assert len(heard) > 0 and np.abs(heard).max() > 0.1  # the callee's tone, at 16 kHz

    await transport.send_audio(np.zeros(320 * 3, dtype=np.float32))
    for _ in range(50):
        if fake.heard:
            break
        await asyncio.sleep(0.01)
    sent = fake.heard[0]
    assert sent["event"] == "media" and sent["streamSid"] == "MZ1"
    media = sent["media"]
    assert isinstance(media, dict)
    assert len(base64.b64decode(str(media["payload"]))) > 0

    await transport.hangup()
    assert transport.close_reason == "caller_hangup"
    assert fake.requests[-1] == (
        "/2010-04-01/Accounts/AC_test/Calls/CA123.json",
        {"Status": ["completed"]},
    )
    fake.hang_up.set()


async def test_the_agent_hanging_up_ends_the_call() -> None:
    fake = FakeTwilio(_free_port())
    transport = _transport(fake)
    await transport.connect("call-2")
    fake.hang_up.set()
    await asyncio.wait_for(transport.closed.wait(), 2)
    assert transport.close_reason == "agent_hangup"
    await transport.hangup()


async def test_missing_credentials_stop_before_any_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TWILIO_AUTH_TOKEN")
    fake = FakeTwilio(_free_port())
    with pytest.raises(TransportError, match="TWILIO_AUTH_TOKEN"):
        await _transport(fake).connect("call-3")
    assert fake.requests == []


async def test_a_refused_call_explains_and_frees_the_port() -> None:
    fake = FakeTwilio(_free_port(), status=400)
    with pytest.raises(TransportError, match="The number is unverified"):
        await _transport(fake).connect("call-4")
    with socket.socket() as s:
        s.bind(("127.0.0.1", fake.port))  # the media server is gone


async def test_an_unanswered_call_is_hung_up() -> None:
    fake = FakeTwilio(_free_port(), answer=False)
    with pytest.raises(TransportError, match="did not answer"):
        await _transport(fake, answer_timeout_s=0.2).connect("call-5")
    assert fake.requests[-1][1] == {"Status": ["completed"]}


async def test_a_stranger_without_the_token_is_turned_away() -> None:
    fake = FakeTwilio(_free_port(), answer=False)
    transport = _transport(fake, answer_timeout_s=1.0)
    connecting = asyncio.create_task(transport.connect("call-6"))
    await asyncio.sleep(0.1)
    async with connect(f"ws://127.0.0.1:{fake.port}/media/guess") as ws:
        with pytest.raises(ConnectionClosed):
            await ws.recv()
        assert ws.close_code == 1008
    with pytest.raises(TransportError):
        await connecting


def test_mulaw_round_trip_keeps_the_signal() -> None:
    tone = (0.5 * np.sin(2 * np.pi * 440 * np.arange(800) / 8000)).astype(np.float32)
    back = mulaw_decode(mulaw_encode(tone))
    assert np.abs(back - tone).max() < 0.02


PHONE_CONFIG = """targets:
  phone:
    transport: twilio
    to_number: "+15550001111"
    from_number: "+15550002222"
    public_url: https://example.ngrok.app
concurrency: {concurrency}
cost_cap_usd: {cap}
"""
SCRIPTED = "id: x\nagent: phone\nmax_duration_s: 150\ncaller: {persona: p, goal: g, script: [hi]}\n"


def test_a_phone_run_warns_and_prices_the_calls_before_dialling(run_cli, write) -> None:
    # A cap below the phone cost stops the run before any call: no request leaves the test.
    write("callback.yaml", PHONE_CONFIG.format(concurrency=1, cap=0.05))
    write("ok.yaml", SCRIPTED)
    done = run_cli("run", "ok.yaml", "--trials", "2")
    assert "Only call numbers you own or have permission to call" in done.stdout
    assert "not legal advice" in done.stdout
    assert "phone ×2 ≤ $0.08" in done.stdout  # 150 s bills as 3 minutes, at $0.014
    assert done.returncode == 2 and "exceeds cost_cap_usd" in done.stderr


def test_missing_twilio_credentials_stop_the_run_before_it_starts(
    run_cli, write, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TWILIO_ACCOUNT_SID")
    write("callback.yaml", PHONE_CONFIG.format(concurrency=1, cap=1.0))
    write("ok.yaml", SCRIPTED)
    done = run_cli("run", "ok.yaml")
    assert done.returncode == 2 and "TWILIO_ACCOUNT_SID" in done.stderr
    assert "PLAN" not in done.stdout


def test_phone_calls_run_one_at_a_time(run_cli, write) -> None:
    write("callback.yaml", PHONE_CONFIG.format(concurrency=4, cap=1.0))
    write("ok.yaml", SCRIPTED)
    done = run_cli("run", "ok.yaml")
    assert done.returncode == 2 and "phone calls run one at a time" in done.stderr


def test_doctor_checks_phone_credentials_without_dialling(
    run_cli, write, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TWILIO_AUTH_TOKEN")
    write("callback.yaml", PHONE_CONFIG.format(concurrency=1, cap=1.0))
    done = run_cli("doctor")
    assert "TWILIO_AUTH_TOKEN is not set" in done.stdout, done.stdout
