import asyncio
import logging
import uuid
from dataclasses import dataclass, field, replace
from urllib.parse import parse_qs, urlsplit

import numpy as np
from websockets.asyncio.server import ServerConnection, serve

from callback_voice.core.paths import model_cache_dir
from callback_voice.providers.stt.faster_whisper_stt import FasterWhisperStt
from callback_voice.providers.tts.cached_tts import CachedTts
from callback_voice.providers.tts.kokoro_tts import KokoroTts
from callback_voice.providers.vad.silero_vad import SileroVad
from callback_voice.reference_agents.restaurant.dialog.agent_flaws import AgentFlaws
from callback_voice.reference_agents.restaurant.dialog.reservation_brain import (
    GREETING,
    REPROMPT,
    ReservationBrain,
)
from callback_voice.reference_agents.restaurant.server.call_registry import CallRegistry
from callback_voice.reference_agents.restaurant.server.http_routes import make_http_routes
from callback_voice.reference_agents.restaurant.voice.agent_session import AgentModels, AgentSession
from callback_voice.reference_agents.restaurant.voice.behavior import AgentBehavior
from callback_voice.reference_agents.restaurant.voice.call_line import CallLine
from callback_voice.reference_agents.restaurant.voice.pick_task_bug import pick_task_bug
from callback_voice.reference_agents.restaurant.voice.speech_chunks import (
    LEAD_PHRASES,
    speech_chunks,
)

log = logging.getLogger("callback.reference_agent")
CALL_ID_HEADER = "X-Callback-Call-Id"


@dataclass(frozen=True, slots=True)
class LiveKitAccess:
    """Where the agent answers LiveKit rooms, and the API key it joins with."""

    url: str
    key: str
    secret: str = field(repr=False)
    room_prefix: str = "callback"


async def serve_agent(
    behavior: AgentBehavior,
    host: str = "127.0.0.1",
    port: int = 8765,
    ready: asyncio.Event | None = None,
    stt_model: str = "base.en",
    livekit: LiveKitAccess | None = None,
) -> None:
    """Run the restaurant agent until cancelled. Loads and warms models before accepting calls.

    It always serves WebSocket calls and HTTP (health, /verify, the talk page) on
    ``port``; with ``livekit`` it also answers new rooms on that LiveKit server.
    """
    stt = FasterWhisperStt(stt_model)
    judge_stt = FasterWhisperStt("tiny.en")
    tts = CachedTts(KokoroTts(behavior.voice), model_cache_dir() / "agent-tts")
    await _warm_up(stt, tts, behavior)
    await judge_stt.transcribe(np.zeros(8000, dtype=np.float32), language="en")
    registry = CallRegistry()

    async def answer(line: CallLine, call_id: str, query: dict[str, list[str]]) -> None:
        store = registry.open(call_id)
        task_bug = pick_task_bug(behavior, call_id, query.get("task_bug", [None])[0])
        call_behavior = behavior
        if query.get("barge_in", [None])[0] == "ignore":
            call_behavior = replace(behavior, barge_in="ignore")
        log.info(
            "call %s connected (%s agent, task bug: %s, interruptions: %s)",
            call_id,
            behavior.name,
            task_bug or "none",
            call_behavior.barge_in,
        )
        flaws = AgentFlaws(
            misread=behavior.misread,
            task_bug=task_bug,
            leaks_other_guests=behavior.leaks_other_guests,
        )
        brain = ReservationBrain(store, flaws=flaws)
        models = AgentModels(stt, judge_stt, tts, SileroVad())
        await AgentSession(line, call_behavior, models, brain).run()
        log.info("call %s ended", call_id)

    async def handle(ws: ServerConnection) -> None:
        call_id = ws.request.headers.get(CALL_ID_HEADER) if ws.request else None
        query = parse_qs(urlsplit(ws.request.path).query) if ws.request else {}
        await answer(ws, call_id or uuid.uuid4().hex[:12], query)

    rooms: asyncio.Task[None] | None = None
    if livekit is not None:
        from callback_voice.reference_agents.restaurant.server.livekit_rooms import (
            watch_livekit_rooms,
        )

        rooms = asyncio.create_task(
            watch_livekit_rooms(
                livekit.url,
                livekit.key,
                livekit.secret,
                livekit.room_prefix,
                lambda line, call_id: answer(line, call_id, {}),
            )
        )

    async with serve(
        handle,
        host,
        port,
        process_request=make_http_routes(registry, behavior.name),
        max_size=2**20,
        ping_interval=None,
    ):
        log.info("restaurant agent (%s) listening on ws://%s:%d", behavior.name, host, port)
        if livekit is not None:
            log.info("answering LiveKit rooms %s-* on %s", livekit.room_prefix, livekit.url)
        if ready is not None:
            ready.set()
        try:
            await (rooms if rooms is not None else asyncio.Future())
        finally:
            if rooms is not None:
                rooms.cancel()


async def _warm_up(stt: FasterWhisperStt, tts: CachedTts, behavior: AgentBehavior) -> None:
    """Load and exercise every model before the first call.

    The TTS engine is run directly: the cached greeting would be a cache hit and leave
    the model cold, so the first new phrase in a call would take over a second. The
    common reply openings are synthesised into the cache so they play at once.
    """
    await stt.transcribe(np.zeros(8000, dtype=np.float32), language="en")
    await tts.inner.synthesize("Warming up.", voice=behavior.voice)
    for chunk in [*speech_chunks(GREETING), *speech_chunks(REPROMPT), *LEAD_PHRASES]:
        await tts.synthesize(chunk, voice=behavior.voice)
