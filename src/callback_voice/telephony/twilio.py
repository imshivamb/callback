"""Twilio: Media Streams (8 kHz mu-law in JSON) and the REST API for outbound calls."""

import base64
import contextlib
import json
import os
from xml.sax.saxutils import quoteattr

import httpx

from callback_voice.audio.format import Audio
from callback_voice.audio.mulaw import mulaw_decode, mulaw_encode
from callback_voice.errors import TransportError
from callback_voice.telephony.dialer import PhoneDialer
from callback_voice.telephony.media_stream import MediaStreamProtocol, StreamEvent

TWILIO_API = "https://api.twilio.com/2010-04-01"
# For local tests against a simulated Twilio only; never needed with a real account.
API_BASE_ENV = "CALLBACK_TWILIO_API_BASE"


class TwilioMediaStream(MediaStreamProtocol):
    """Twilio Media Streams: JSON text messages, audio as base64 8 kHz G.711 mu-law."""

    name = "twilio"
    sample_rate = 8_000

    def parse(self, message: str | bytes) -> StreamEvent:
        event = json.loads(message)
        kind = event.get("event")
        if kind == "start":
            start = event.get("start") or {}
            return StreamEvent(
                "start",
                stream_id=event.get("streamSid") or start.get("streamSid"),
                call_ref=start.get("callSid"),
                parameters={
                    str(k): str(v) for k, v in (start.get("customParameters") or {}).items()
                },
            )
        if kind == "media":
            media = event.get("media") or {}
            if media.get("track", "inbound") != "inbound":
                return StreamEvent("other")
            return StreamEvent("media", audio=mulaw_decode(base64.b64decode(media["payload"])))
        if kind == "dtmf":
            return StreamEvent("dtmf", digits=str((event.get("dtmf") or {}).get("digit", "")))
        if kind == "stop":
            return StreamEvent("stop")
        return StreamEvent("other")

    def media(self, stream_id: str, audio: Audio) -> str:
        payload = base64.b64encode(mulaw_encode(audio)).decode("ascii")
        return json.dumps({"event": "media", "streamSid": stream_id, "media": {"payload": payload}})


def stream_twiml(stream_url: str, parameters: dict[str, str] | None = None) -> str:
    """TwiML that connects a call's audio to ``stream_url`` both ways."""
    params = "".join(
        f"<Parameter name={quoteattr(k)} value={quoteattr(v)}/>"
        for k, v in (parameters or {}).items()
    )
    return (
        f"<Response><Connect><Stream url={quoteattr(stream_url)}>{params}</Stream>"
        "</Connect></Response>"
    )


class TwilioDialer(PhoneDialer):
    """Places calls with Twilio's REST API. Twilio bills per started minute."""

    name = "twilio"

    def __init__(
        self,
        account_sid_env: str = "TWILIO_ACCOUNT_SID",
        auth_token_env: str = "TWILIO_AUTH_TOKEN",
        *,
        http: httpx.AsyncClient | None = None,
        api_base: str | None = None,
    ) -> None:
        self._envs = (account_sid_env, auth_token_env)
        self._http = http
        self._owns_http = http is None
        self._api_base = (api_base or os.environ.get(API_BASE_ENV) or TWILIO_API).rstrip("/")

    def check_credentials(self) -> None:
        self._auth()

    async def place_call(
        self, to_number: str, from_number: str, stream_url: str, call_id: str
    ) -> str:
        auth = self._auth()
        data = {
            "To": to_number,
            "From": from_number,
            "Twiml": stream_twiml(stream_url, {"callback_call_id": call_id}),
        }
        try:
            response = await self._client().post(self._calls_url(auth[0]), data=data, auth=auth)
        except httpx.HTTPError as exc:
            raise TransportError(f"cannot reach Twilio: {exc}") from exc
        if response.status_code >= 400:
            try:
                detail = response.json().get("message", response.text)
            except ValueError:
                detail = response.text
            raise TransportError(
                f"Twilio refused the call ({response.status_code}): {detail}",
                hint="trial accounts can only call verified numbers",
            )
        return str(response.json()["sid"])

    async def end_call(self, call_ref: str) -> None:
        auth = self._auth()
        with contextlib.suppress(httpx.HTTPError):
            await self._client().post(
                self._calls_url(auth[0], call_ref), data={"Status": "completed"}, auth=auth
            )

    async def close(self) -> None:
        if self._owns_http and self._http is not None:
            await self._http.aclose()

    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=15.0)
        return self._http

    def _auth(self) -> tuple[str, str]:
        values = [os.environ.get(name, "") for name in self._envs]
        missing = [name for name, value in zip(self._envs, values, strict=True) if not value]
        if missing:
            raise TransportError(
                f"phone calls need {' and '.join(missing)} set",
                hint="copy them from the Twilio console; Callback reads them only from the environment",
            )
        return values[0], values[1]

    def _calls_url(self, account_sid: str, call_ref: str | None = None) -> str:
        base = f"{self._api_base}/Accounts/{account_sid}/Calls"
        return f"{base}/{call_ref}.json" if call_ref else f"{base}.json"
