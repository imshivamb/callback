import asyncio
import contextlib
import secrets
from urllib.parse import urlsplit

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from callback_voice.audio.format import SAMPLE_RATE, Audio
from callback_voice.audio.stream_resampler import StreamResampler
from callback_voice.errors import TransportError
from callback_voice.telephony.dialer import PhoneDialer
from callback_voice.telephony.media_stream import MediaStreamProtocol
from callback_voice.transports.base import Transport

ANSWER_TIMEOUT_S = 60.0


class PhoneTransport(Transport):
    """An outbound phone call through any provider with a media-stream API.

    Callback serves a WebSocket on ``listen_port``, asks the provider (``dialer``) to
    call ``to_number`` and stream the call to ``public_url`` (a tunnel to that port),
    and exchanges audio in the provider's format (``protocol``). The stream URL
    carries a random token, so nothing else that finds the tunnel can join the call.
    """

    def __init__(
        self,
        protocol: MediaStreamProtocol,
        dialer: PhoneDialer,
        *,
        to_number: str,
        from_number: str,
        public_url: str,
        listen_port: int,
        answer_timeout_s: float = ANSWER_TIMEOUT_S,
    ) -> None:
        super().__init__()
        self.name = protocol.name
        self._protocol = protocol
        self._dialer = dialer
        self._to, self._from = to_number, from_number
        self._public_url = public_url
        self._port = listen_port
        self._answer_timeout_s = answer_timeout_s
        self._token = secrets.token_urlsafe(16)
        self._server: Server | None = None
        self._ws: ServerConnection | None = None
        self._stream_id: str | None = None
        self._call_ref: str | None = None
        self._ready = asyncio.Event()
        self._ended = False
        self._to_wire = StreamResampler(SAMPLE_RATE, protocol.sample_rate)
        self._from_wire = StreamResampler(protocol.sample_rate, SAMPLE_RATE)

    @property
    def stream_url(self) -> str:
        public = urlsplit(self._public_url)
        return f"wss://{public.netloc}{public.path.rstrip('/')}/media/{self._token}"

    async def connect(self, call_id: str) -> None:
        self._dialer.check_credentials()
        try:
            self._server = await serve(self._handle, "127.0.0.1", self._port, ping_interval=None)
        except OSError as exc:
            raise TransportError(
                f"cannot listen on port {self._port}: {exc}",
                hint="another call or program uses it; change listen_port in callback.yaml",
            ) from exc
        try:
            self._call_ref = await self._dialer.place_call(
                self._to, self._from, self.stream_url, call_id
            )
            await asyncio.wait_for(self._ready.wait(), self._answer_timeout_s)
        except TimeoutError as exc:
            await self.hangup()
            raise TransportError(
                f"{self._to} did not answer within {self._answer_timeout_s:g} s",
                hint="check the number, and that public_url tunnels to listen_port",
            ) from exc
        except TransportError:
            await self.hangup()
            raise
        if self._stream_id is None:
            await self.hangup()
            raise TransportError(
                "the call ended before any audio was streamed",
                hint="check the number, and that public_url tunnels to listen_port",
            )

    async def send_audio(self, audio: Audio) -> None:
        if self._ws is None or self._stream_id is None or self.closed.is_set():
            return
        message = self._protocol.media(self._stream_id, self._to_wire.process(audio))
        with contextlib.suppress(ConnectionClosed):
            await self._ws.send(message)

    async def send_dtmf(self, digits: str) -> bool:
        return False  # media streams carry audio only; the caller plays in-band tones

    async def hangup(self) -> None:
        if self._ended:
            return
        self._ended = True
        self.mark_closed("caller_hangup")
        if self._call_ref is not None:
            with contextlib.suppress(TransportError):
                await self._dialer.end_call(self._call_ref)
        if self._ws is not None:
            with contextlib.suppress(ConnectionClosed):
                await self._ws.close(1000, "caller hung up")
        if self._server is not None:
            self._server.close()
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self._server.wait_closed(), 5)
        await self._dialer.close()

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
                event = self._protocol.parse(message)
                if event.kind == "start":
                    self._stream_id = event.stream_id or ""
                    self._ready.set()
                elif event.kind == "media" and event.audio is not None:
                    self.inbound.put_nowait(self._from_wire.process(event.audio))
                elif event.kind == "stop":
                    break
            self.mark_closed("agent_hangup")
        except ConnectionClosed as closed:
            self.mark_closed(f"connection_lost ({closed})")
        finally:
            self._ready.set()  # wake connect() if the stream ended before it started
