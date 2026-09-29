import asyncio
import contextlib

from livekit import api, rtc

from callback_voice.audio.format import FRAME_MS, SAMPLE_RATE, Audio
from callback_voice.audio.pcm import from_pcm16, to_pcm16
from callback_voice.core.config.target_config import LiveKitTarget
from callback_voice.errors import TransportError
from callback_voice.transports.base import Transport
from callback_voice.transports.livekit_room import (
    CALLER_IDENTITY,
    credentials,
    http_url,
    join_token,
    room_metadata,
    room_name,
)

_JOIN_TIMEOUT_S = 10.0
_AGENT_TIMEOUT_S = 20.0
_DTMF_CODES = {**{str(d): d for d in range(10)}, "*": 10, "#": 11}


class LiveKitTransport(Transport):
    """A LiveKit room: Callback creates it, joins as the caller, and waits for the agent.

    The room is named ``<room_prefix>-<call_id>`` and carries the call id in its
    metadata, so an agent dispatched to it can tie its end state to the call. Audio
    goes over WebRTC as the agent would hear a real participant; the SDK resamples
    both ways at 16 kHz mono. Hanging up deletes the room, which disconnects the agent.
    """

    name = "livekit"

    def __init__(self, target: LiveKitTarget) -> None:
        super().__init__()
        self._target = target
        self._room: rtc.Room | None = None
        self._source: rtc.AudioSource | None = None
        self._api: api.LiveKitAPI | None = None
        self._room_name = ""
        self._agent_identity: str | None = None
        self._agent_track = asyncio.Event()
        self._reader: asyncio.Task[None] | None = None
        self._hung_up = False

    async def connect(self, call_id: str) -> None:
        key, secret = credentials(self._target.api_key_env, self._target.api_secret_env)
        self._room_name = room_name(self._target.room_prefix, call_id)
        self._api = api.LiveKitAPI(http_url(self._target.url), key, secret)
        self._room = rtc.Room()
        self._source = rtc.AudioSource(SAMPLE_RATE, 1, queue_size_ms=200)
        self._room.on("track_subscribed", self._on_track)
        self._room.on("participant_disconnected", self._on_participant_left)
        self._room.on("disconnected", self._on_disconnected)
        try:
            await asyncio.wait_for(self._join(key, secret, call_id), _JOIN_TIMEOUT_S)
        except Exception as exc:
            await self._cleanup()
            raise TransportError(
                f"cannot join LiveKit room {self._room_name} at {self._target.url}: "
                f"{exc or type(exc).__name__}",
                hint="is the LiveKit server running? `callback doctor` checks every target",
            ) from exc
        try:
            await asyncio.wait_for(self._agent_track.wait(), _AGENT_TIMEOUT_S)
        except TimeoutError as exc:
            await self._cleanup()
            who = self._target.agent_identity or "any agent"
            raise TransportError(
                f"{who} did not join LiveKit room {self._room_name} with audio "
                f"within {_AGENT_TIMEOUT_S:.0f} s",
                hint=f"is your agent dispatched to rooms named {self._target.room_prefix}-…?",
            ) from exc

    async def _join(self, key: str, secret: str, call_id: str) -> None:
        assert self._api is not None and self._room is not None and self._source is not None
        await self._api.room.create_room(
            api.CreateRoomRequest(
                name=self._room_name,
                metadata=room_metadata(call_id),
                empty_timeout=30,
                departure_timeout=5,
            )
        )
        await self._room.connect(
            self._target.url, join_token(key, secret, CALLER_IDENTITY, self._room_name)
        )
        track = rtc.LocalAudioTrack.create_audio_track("caller", self._source)
        await self._room.local_participant.publish_track(
            track, rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
        )

    def _on_track(
        self,
        track: rtc.Track,
        _publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ) -> None:
        if track.kind != rtc.TrackKind.KIND_AUDIO or self._agent_identity is not None:
            return
        wanted = self._target.agent_identity
        if wanted is not None and participant.identity != wanted:
            return
        self._agent_identity = participant.identity
        self._reader = asyncio.create_task(self._read(track))
        self._agent_track.set()

    def _on_participant_left(self, participant: rtc.RemoteParticipant) -> None:
        if participant.identity == self._agent_identity:
            self.mark_closed("agent_hangup")

    def _on_disconnected(self, reason: object) -> None:
        if not self._hung_up:
            self.mark_closed(f"connection_lost ({reason})")

    async def _read(self, track: rtc.Track) -> None:
        stream = rtc.AudioStream(
            track, sample_rate=SAMPLE_RATE, num_channels=1, frame_size_ms=FRAME_MS
        )
        try:
            async for event in stream:
                self.inbound.put_nowait(from_pcm16(bytes(event.frame.data)))
        finally:
            await stream.aclose()

    async def send_audio(self, audio: Audio) -> None:
        if self.closed.is_set() or self._agent_identity is None or self._source is None:
            return
        pcm = to_pcm16(audio)
        frame = rtc.AudioFrame(pcm, SAMPLE_RATE, 1, len(pcm) // 2)
        with contextlib.suppress(Exception):  # the room went away mid-frame
            await self._source.capture_frame(frame)

    async def send_dtmf(self, digits: str) -> bool:
        if self.closed.is_set() or self._room is None:
            return False
        for digit in digits:
            if digit in _DTMF_CODES:
                with contextlib.suppress(Exception):
                    await self._room.local_participant.publish_dtmf(
                        code=_DTMF_CODES[digit], digit=digit
                    )
        return False  # also play tones in-band: most agents only hear audio

    async def hangup(self) -> None:
        self.mark_closed("caller_hangup")
        await self._cleanup()

    async def _cleanup(self) -> None:
        if self._hung_up:
            return
        self._hung_up = True
        if self._reader is not None:
            self._reader.cancel()
        if self._room is not None:
            with contextlib.suppress(Exception):
                await self._room.disconnect()
        if self._api is not None:
            with contextlib.suppress(Exception):
                await self._api.room.delete_room(api.DeleteRoomRequest(room=self._room_name))
            await self._api.aclose()
        if self._source is not None:
            with contextlib.suppress(Exception):
                await self._source.aclose()
