import asyncio
import logging
import uuid
from dataclasses import replace
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
from callback_voice.reference_agents.restaurant.voice.pick_task_bug import pick_task_bug
from callback_voice.reference_agents.restaurant.voice.split_sentences import split_sentences

log = logging.getLogger("callback.reference_agent")
CALL_ID_HEADER = "X-Callback-Call-Id"


async def serve_agent(
    behavior: AgentBehavior,
    host: str = "127.0.0.1",
    port: int = 8765,
    ready: asyncio.Event | None = None,
    stt_model: str = "base.en",
) -> None:
    """Run the restaurant agent until cancelled. Loads and warms models before accepting calls."""
    stt = FasterWhisperStt(stt_model)
    judge_stt = FasterWhisperStt("tiny.en")
    tts = CachedTts(KokoroTts(behavior.voice), model_cache_dir() / "agent-tts")
    await _warm_up(stt, tts, behavior)
    await judge_stt.transcribe(np.zeros(8000, dtype=np.float32), language="en")
    registry = CallRegistry()

    async def handle(ws: ServerConnection) -> None:
        call_id = ws.request.headers.get(CALL_ID_HEADER) if ws.request else None
        call_id = call_id or uuid.uuid4().hex[:12]
        store = registry.open(call_id)
        query = parse_qs(urlsplit(ws.request.path).query) if ws.request else {}
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
        await AgentSession(ws, call_behavior, models, brain).run()
        log.info("call %s ended", call_id)

    async with serve(
        handle,
        host,
        port,
        process_request=make_http_routes(registry, behavior.name),
        max_size=2**20,
        ping_interval=None,
    ):
        log.info("restaurant agent (%s) listening on ws://%s:%d", behavior.name, host, port)
        if ready is not None:
            ready.set()
        await asyncio.Future()


async def _warm_up(stt: FasterWhisperStt, tts: CachedTts, behavior: AgentBehavior) -> None:
    """Load and exercise every model before the first call.

    The TTS engine is run directly: the cached greeting would be a cache hit and leave
    the model cold, so the first new phrase in a call would take over a second.
    """
    await stt.transcribe(np.zeros(8000, dtype=np.float32), language="en")
    await tts.inner.synthesize("Warming up.", voice=behavior.voice)
    for sentence in [*split_sentences(GREETING), *split_sentences(REPROMPT)]:
        await tts.synthesize(sentence, voice=behavior.voice)
