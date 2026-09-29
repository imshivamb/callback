import asyncio
import contextlib
import json
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable

from livekit import api, rtc

from callback_voice.audio.format import FRAME_MS, SAMPLE_RATE
from callback_voice.transports.livekit_room import CALLER_IDENTITY, http_url, join_token

log = logging.getLogger("callback.reference_agent")
AGENT_IDENTITY = "restaurant-agent"
_POLL_S = 0.2
_FRESH_ROOM_S = 30
_CALLER_TIMEOUT_S = 10.0

type AnswerCall = Callable[["LiveKitLine", str], Awaitable[None]]


class LiveKitLine:
    """The agent's end of a call in a LiveKit room (a ``CallLine``).

    Audio in comes from the caller's track, audio out goes to the agent's own track;
    the call ends when the caller leaves or the room is deleted.
    """

    def __init__(self, room: rtc.Room, source: rtc.AudioSource) -> None:
        self._room = room
        self._source = source
        self._frames: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._reader: asyncio.Task[None] | None = None
        self._closed = False

    @classmethod
    async def join(cls, url: str, token: str) -> "LiveKitLine":
        """Join, publish the agent's voice, and return once the caller hears it."""
        room = rtc.Room()
        source = rtc.AudioSource(SAMPLE_RATE, 1, queue_size_ms=200)
        line = cls(room, source)
        caller_track: asyncio.Future[rtc.Track] = asyncio.get_running_loop().create_future()
        heard = asyncio.Event()

        def _on_track(track: rtc.Track, _pub: object, who: rtc.RemoteParticipant) -> None:
            if (
                track.kind == rtc.TrackKind.KIND_AUDIO
                and who.identity == CALLER_IDENTITY
                and not caller_track.done()
            ):
                caller_track.set_result(track)

        room.on("track_subscribed", _on_track)
        room.on("local_track_subscribed", lambda _track: heard.set())
        room.on("participant_disconnected", line._on_left)
        room.on("disconnected", lambda _reason: line._end())
        try:
            await room.connect(url, token)
            track = rtc.LocalAudioTrack.create_audio_track("agent", source)
            await room.local_participant.publish_track(
                track, rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
            )
            incoming = await asyncio.wait_for(caller_track, _CALLER_TIMEOUT_S)
            await asyncio.wait_for(heard.wait(), _CALLER_TIMEOUT_S)
        except BaseException:
            await line.close()
            raise
        line._reader = asyncio.create_task(line._read(incoming))
        return line

    def _on_left(self, participant: rtc.RemoteParticipant) -> None:
        if participant.identity == CALLER_IDENTITY:
            self._end()

    def _end(self) -> None:
        self._frames.put_nowait(None)

    async def _read(self, track: rtc.Track) -> None:
        stream = rtc.AudioStream(
            track, sample_rate=SAMPLE_RATE, num_channels=1, frame_size_ms=FRAME_MS
        )
        try:
            async for event in stream:
                self._frames.put_nowait(bytes(event.frame.data))
        finally:
            await stream.aclose()

    async def __aiter__(self) -> AsyncIterator[bytes | str]:
        while (frame := await self._frames.get()) is not None:
            yield frame

    async def send(self, message: bytes) -> None:
        if self._closed:
            return
        frame = rtc.AudioFrame(message, SAMPLE_RATE, 1, len(message) // 2)
        with contextlib.suppress(Exception):  # the room went away mid-frame
            await self._source.capture_frame(frame)

    async def close(self) -> None:
        """Leave the room (the agent hangs up). Idempotent."""
        if self._closed:
            return
        self._closed = True
        self._end()
        if self._reader is not None:
            self._reader.cancel()
        with contextlib.suppress(Exception):
            await self._room.disconnect()
        with contextlib.suppress(Exception):
            await self._source.aclose()


async def watch_livekit_rooms(
    url: str, key: str, secret: str, prefix: str, answer: AnswerCall
) -> None:
    """Answer every new room named ``<prefix>-…`` on a LiveKit server, until cancelled.

    Polls the server's room list: simple, and needs no webhook configuration on a
    self-hosted server. A call's id comes from the room metadata Callback sets, or else
    from the room name. Rooms older than 30 s when first seen are left alone.
    """
    lk = api.LiveKitAPI(http_url(url), key, secret)
    seen: set[str] = set()
    calls: set[asyncio.Task[None]] = set()
    try:
        while True:
            listing = await lk.room.list_rooms(api.ListRoomsRequest())
            for room in listing.rooms:
                if room.sid in seen or not room.name.startswith(f"{prefix}-"):
                    continue
                seen.add(room.sid)
                if time.time() - room.creation_time > _FRESH_ROOM_S:
                    continue
                call_id = _call_id(room.metadata) or room.name.removeprefix(f"{prefix}-")
                token = join_token(key, secret, AGENT_IDENTITY, room.name)
                task = asyncio.create_task(_answer_room(url, token, room.name, call_id, answer))
                calls.add(task)
                task.add_done_callback(calls.discard)
            await asyncio.sleep(_POLL_S)
    finally:
        for task in calls:
            task.cancel()
        await lk.aclose()


async def _answer_room(url: str, token: str, name: str, call_id: str, answer: AnswerCall) -> None:
    try:
        line = await LiveKitLine.join(url, token)
    except Exception as exc:
        log.warning("could not answer LiveKit room %s: %s", name, exc or type(exc).__name__)
        return
    try:
        await answer(line, call_id)
    finally:
        await line.close()


def _call_id(metadata: str) -> str | None:
    with contextlib.suppress(ValueError, AttributeError):
        value = json.loads(metadata).get("callback_call_id")
        return str(value) if value else None
    return None
