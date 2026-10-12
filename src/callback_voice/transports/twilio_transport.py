import asyncio
import base64
import contextlib
import json
import os
import secrets
from urllib.parse import urlsplit
from xml.sax.saxutils import quoteattr

import httpx
from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from callback_voice.audio.format import SAMPLE_RATE, Audio
from callback_voice.audio.mulaw import mulaw_decode, mulaw_encode
from callback_voice.audio.stream_resampler import StreamResampler
from callback_voice.core.config.target_config import TwilioTarget
from callback_voice.errors import TransportError
from callback_voice.transports.base import Transport

TWILIO_API = "https://api.twilio.com/2010-04-01"
WIRE_RATE = 8_000  # Media Streams carry 8 kHz G.711 mu-law
ANSWER_TIMEOUT_S = 60.0


class TwilioTransport(Transport):
    """An outbound phone call through Twilio, with audio over Media Streams.

    Callback serves a WebSocket on ``listen_port`` and asks Twilio's REST API to call
    ``to_number`` with ``<Connect><Stream>`` pointing at ``public_url`` (a tunnel to
    that port). Once the call is answered, Twilio streams the agent's audio as 8 kHz
    mu-law JSON frames and plays back what Callback sends the same way. The stream URL
    carries a random token, so nothing else that finds the tunnel can join the call.
    Twilio bills the account per started minute.
    """

    name = "twilio"

    def __init__(
        self,
        target: TwilioTarget,
        *,
        http: httpx.AsyncClient | None = None,
        api_base: str = TWILIO_API,
        answer_timeout_s: float = ANSWER_TIMEOUT_S,
    ) -> None:
        super().__init__()
        self._target = target
        self._http = http
        self._owns_http = http is None
        self._api_base = api_base.rstrip("/")
        self._answer_timeout_s = answer_timeout_s
        self._token = secrets.token_urlsafe(16)
        self._auth: tuple[str, str] | None = None
        self._server: Server | None = None
        self._ws: ServerConnection | None = None
        self._stream_sid: str | None = None
        self._call_sid: str | None = None
        self._ready = asyncio.Event()
        self._ended = False
        self._to_wire = StreamResampler(SAMPLE_RATE, WIRE_RATE)
        self._from_wire = StreamResampler(WIRE_RATE, SAMPLE_RATE)

    @property
    def stream_url(self) -> str:
        public = urlsplit(self._target.public_url)
        return f"wss://{public.netloc}{public.path.rstrip('/')}/media/{self._token}"

    async def connect(self, call_id: str) -> None:
        self._auth = self._credentials()
        try:
            self._server = await serve(
                self._handle, "127.0.0.1", self._target.listen_port, ping_interval=None
            )
        except OSError as exc:
            raise TransportError(
                f"cannot listen on port {self._target.listen_port}: {exc}",
                hint="another call or program uses it; change listen_port in callback.yaml",
            ) from exc
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=15.0)
        try:
            self._call_sid = await self._place_call(call_id)
            await asyncio.wait_for(self._ready.wait(), self._answer_timeout_s)
        except TimeoutError as exc:
            await self.hangup()
            raise TransportError(
                f"{self._target.to_number} did not answer within {self._answer_timeout_s:g} s",
                hint="check the number, and that public_url tunnels to listen_port",
            ) from exc
        except TransportError:
            await self.hangup()
            raise
        if self._stream_sid is None:
            await self.hangup()
            raise TransportError(
                "the call ended before any audio was streamed",
                hint="check the number, and that public_url tunnels to listen_port",
            )

    async def send_audio(self, audio: Audio) -> None:
        if self._ws is None or self._stream_sid is None or self.closed.is_set():
            return
        payload = base64.b64encode(mulaw_encode(self._to_wire.process(audio))).decode("ascii")
        message = {"event": "media", "streamSid": self._stream_sid, "media": {"payload": payload}}
        with contextlib.suppress(ConnectionClosed):
            await self._ws.send(json.dumps(message))

    async def send_dtmf(self, digits: str) -> bool:
        return False  # Media Streams cannot send digits; the caller plays in-band tones

    async def hangup(self) -> None:
        if self._ended:
            return
        self._ended = True
        self.mark_closed("caller_hangup")
        if self._call_sid is not None and self._http is not None and self._auth is not None:
            with contextlib.suppress(httpx.HTTPError):
                await self._http.post(
                    self._calls_url(self._call_sid), data={"Status": "completed"}, auth=self._auth
                )
        if self._ws is not None:
            with contextlib.suppress(ConnectionClosed):
                await self._ws.close(1000, "caller hung up")
        if self._server is not None:
            self._server.close()
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self._server.wait_closed(), 5)
        if self._owns_http and self._http is not None:
            await self._http.aclose()

    def _credentials(self) -> tuple[str, str]:
        names = (self._target.account_sid_env, self._target.auth_token_env)
        values = [os.environ.get(name, "") for name in names]
        missing = [name for name, value in zip(names, values, strict=True) if not value]
        if missing:
            raise TransportError(
                f"phone calls need {' and '.join(missing)} set",
                hint="copy them from the Twilio console; Callback reads them only from the environment",
            )
        return values[0], values[1]

    def _calls_url(self, call_sid: str | None = None) -> str:
        assert self._auth is not None
        base = f"{self._api_base}/Accounts/{self._auth[0]}/Calls"
        return f"{base}/{call_sid}.json" if call_sid else f"{base}.json"

    async def _place_call(self, call_id: str) -> str:
        assert self._http is not None and self._auth is not None
        twiml = (
            f"<Response><Connect><Stream url={quoteattr(self.stream_url)}>"
            f'<Parameter name="callback_call_id" value={quoteattr(call_id)}/>'
            "</Stream></Connect></Response>"
        )
        data = {"To": self._target.to_number, "From": self._target.from_number, "Twiml": twiml}
        try:
            response = await self._http.post(self._calls_url(), data=data, auth=self._auth)
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

    async def _handle(self, ws: ServerConnection) -> None:
        if not ws.request or not ws.request.path.rstrip("/").endswith(f"/media/{self._token}"):
            await ws.close(1008, "unknown stream")
            return
        if self._ws is not None:
            await ws.close(1008, "call already connected")
            return
        self._ws = ws
        try:
            async for message in ws:
                if not self._on_event(json.loads(message)):
                    break
            self.mark_closed("agent_hangup")
        except ConnectionClosed as closed:
            self.mark_closed(f"connection_lost ({closed})")
        finally:
            self._ready.set()  # wake connect() if the stream ended before it started

    def _on_event(self, event: dict[str, object]) -> bool:
        """Handle one Media Streams message. Returns False when the stream has stopped."""
        kind = event.get("event")
        if kind == "start":
            start = event.get("start")
            sid = event.get("streamSid") or (
                start.get("streamSid") if isinstance(start, dict) else None
            )
            self._stream_sid = str(sid) if sid else None
            self._ready.set()
        elif kind == "media":
            media = event.get("media")
            if isinstance(media, dict) and media.get("track", "inbound") == "inbound":
                audio = mulaw_decode(base64.b64decode(str(media["payload"])))
                self.inbound.put_nowait(self._from_wire.process(audio))
        elif kind == "stop":
            return False
        return True
