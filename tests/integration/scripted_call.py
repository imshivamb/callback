"""Helpers shared by integration tests: run the reference agent and place one scripted call."""

import asyncio
import socket
from pathlib import Path

from callback_voice.caller.brain.scripted_brain import ScriptedBrain
from callback_voice.caller.engine.call_session import CallOutcome, CallSession, CallSetup
from callback_voice.caller.speech.caller_speech import CallerSpeech
from callback_voice.core.config.target_config import WebSocketTarget
from callback_voice.core.models.caller_spec import CallerSpec
from callback_voice.core.paths import model_cache_dir
from callback_voice.providers.tts.cached_tts import CachedTts
from callback_voice.providers.tts.kokoro_tts import KokoroTts
from callback_voice.providers.vad.silero_vad import SileroVad
from callback_voice.reference_agents.restaurant.server.serve_agent import serve_agent
from callback_voice.reference_agents.restaurant.voice.behavior import AgentBehavior
from callback_voice.transports.websocket_transport import WebSocketTransport

MOVE_SCRIPT = (
    "Hi, I need to move my booking to Saturday.",
    "It's D X 7 Q 2.",
    "Anytime between seven and nine is fine.",
    "Seven thirty works.",
    "Yes please.",
    "No, that's all. Thanks, bye.",
)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


async def call_reference_agent(
    behavior: AgentBehavior, out_dir: Path, call_id: str, script: tuple[str, ...] = MOVE_SCRIPT
) -> tuple[CallOutcome, int]:
    port = free_port()
    ready = asyncio.Event()
    server = asyncio.create_task(serve_agent(behavior, port=port, ready=ready))
    await asyncio.wait_for(ready.wait(), 300)
    try:
        spec = CallerSpec(persona="Priya", goal="move booking", voice="male_us_1", script=script)
        tts = CachedTts(KokoroTts(), model_cache_dir() / "caller-tts-test")
        setup = CallSetup(
            call_id=call_id,
            spec=spec,
            max_duration_s=120,
            transport=WebSocketTransport(WebSocketTarget(url=f"ws://127.0.0.1:{port}/")),
            brain=ScriptedBrain(script),
            speech=CallerSpeech(tts, spec),
            make_vad=SileroVad,
        )
        outcome = await CallSession(setup).run()
        outcome.recorder.save(out_dir)
        outcome.log.save(out_dir / "events.jsonl")
        return outcome, port
    finally:
        server.cancel()


if __name__ == "__main__":
    import sys

    from callback_voice.reference_agents.restaurant.voice.behavior import BEHAVIORS

    out = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/cb-call")
    result, _ = asyncio.run(call_reference_agent(BEHAVIORS[sys.argv[1]], out, "manual-1"))
    print(
        result.end_reason, round(result.duration_s, 2), "lateness", round(result.max_lateness_s, 4)
    )
    for e in result.log.events:
        print(
            f"{e.t_s:7.2f} {e.kind:17} {e.end_s or '':8} {e.chaos_type or ''} {e.text or ''} {e.data or ''}"
        )
