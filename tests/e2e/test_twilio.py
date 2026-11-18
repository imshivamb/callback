"""Twilio specifics: the REST dialer, the Media Streams format, and the CLI's phone safety."""

import base64
import json
from urllib.parse import parse_qs

import httpx
import numpy as np
import pytest

from callback_voice.audio.mulaw import mulaw_decode, mulaw_encode
from callback_voice.errors import TransportError
from callback_voice.telephony.twilio import API_BASE_ENV, TwilioDialer, TwilioMediaStream


@pytest.fixture(autouse=True)
def credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC_test")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "secret")
    monkeypatch.delenv(API_BASE_ENV, raising=False)


class FakeRest:
    def __init__(self, status: int = 201) -> None:
        self.status = status
        self.requests: list[tuple[str, dict[str, list[str]], str]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(
            (request.url.path, parse_qs(request.content.decode()), request.headers["authorization"])
        )
        if self.status >= 400:
            return httpx.Response(self.status, json={"message": "The number is unverified"})
        return httpx.Response(201, json={"sid": "CA123"})


def _dialer(rest: FakeRest, **kwargs: str) -> TwilioDialer:
    return TwilioDialer(http=httpx.AsyncClient(transport=httpx.MockTransport(rest)), **kwargs)


async def test_placing_a_call_sends_the_stream_twiml() -> None:
    rest = FakeRest()
    sid = await _dialer(rest).place_call(
        "+15550001111", "+15550002222", "wss://x.app/media/t0k", "c-1"
    )
    path, form, auth = rest.requests[0]
    assert sid == "CA123"
    assert path == "/2010-04-01/Accounts/AC_test/Calls.json"
    assert auth == "Basic " + base64.b64encode(b"AC_test:secret").decode()
    assert form["To"] == ["+15550001111"] and form["From"] == ["+15550002222"]
    assert form["Twiml"] == [
        '<Response><Connect><Stream url="wss://x.app/media/t0k">'
        '<Parameter name="callback_call_id" value="c-1"/></Stream></Connect></Response>'
    ]


async def test_ending_a_call_completes_it() -> None:
    rest = FakeRest()
    await _dialer(rest).end_call("CA123")
    assert rest.requests[0][:2] == (
        "/2010-04-01/Accounts/AC_test/Calls/CA123.json",
        {"Status": ["completed"]},
    )


async def test_a_refused_call_says_why() -> None:
    with pytest.raises(TransportError, match="The number is unverified"):
        await _dialer(FakeRest(status=400)).place_call("+1555", "+1556", "wss://x/media/t", "c")


def test_missing_credentials_are_named(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TWILIO_AUTH_TOKEN")
    with pytest.raises(TransportError, match="TWILIO_AUTH_TOKEN"):
        TwilioDialer().check_credentials()


async def test_a_simulated_twilio_can_stand_in_for_the_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(API_BASE_ENV, "http://127.0.0.1:9/2010-04-01")
    rest = FakeRest()
    await _dialer(rest).place_call("+1555", "+1556", "wss://x/media/t", "c")
    assert rest.requests[0][0] == "/2010-04-01/Accounts/AC_test/Calls.json"


def test_media_stream_messages_round_trip() -> None:
    stream = TwilioMediaStream()
    start = stream.parse(
        json.dumps(
            {
                "event": "start",
                "start": {
                    "streamSid": "MZ1",
                    "callSid": "CA1",
                    "customParameters": {"callback_call_id": "c-1"},
                },
            }
        )
    )
    assert (start.kind, start.stream_id, start.call_ref) == ("start", "MZ1", "CA1")
    assert start.parameters == {"callback_call_id": "c-1"}
    tone = (0.5 * np.sin(2 * np.pi * 440 * np.arange(160) / 8000)).astype(np.float32)
    sent = json.loads(stream.media("MZ1", tone))
    assert sent["event"] == "media" and sent["streamSid"] == "MZ1"
    back = stream.parse(
        json.dumps(
            {"event": "media", "media": {"track": "inbound", "payload": sent["media"]["payload"]}}
        )
    )
    assert (
        back.kind == "media" and back.audio is not None and np.abs(back.audio - tone).max() < 0.02
    )
    outbound = json.dumps(
        {"event": "media", "media": {"track": "outbound", "payload": sent["media"]["payload"]}}
    )
    assert stream.parse(outbound).kind == "other"
    assert stream.parse(json.dumps({"event": "dtmf", "dtmf": {"digit": "5"}})).digits == "5"
    assert stream.parse(json.dumps({"event": "stop"})).kind == "stop"


def test_mulaw_round_trip_keeps_the_signal() -> None:
    tone = (0.5 * np.sin(2 * np.pi * 440 * np.arange(800) / 8000)).astype(np.float32)
    assert np.abs(mulaw_decode(mulaw_encode(tone)) - tone).max() < 0.02


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
