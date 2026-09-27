import contextlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from callback_voice.audio.format import Audio
from callback_voice.caller.brain.base import CallerBrain
from callback_voice.caller.engine.agent_listener import (
    AgentListener,
    AgentTurnEnded,
    AgentTurnStarted,
)
from callback_voice.caller.engine.caller_voice import CallerVoice
from callback_voice.caller.engine.conversation import Conversation
from callback_voice.caller.engine.playout_buffer import PlayoutBuffer
from callback_voice.caller.engine.tick_clock import TickClock
from callback_voice.caller.engine.utterance import Utterance, UtteranceTag
from callback_voice.caller.speech.caller_speech import CallerSpeech
from callback_voice.chaos.processors.chaos_processor import ChaosProcessor
from callback_voice.core.models.caller_spec import CallerSpec
from callback_voice.core.models.chaos_event import ChaosEvent
from callback_voice.errors import CallbackError
from callback_voice.providers.stt.base import SpeechToText
from callback_voice.providers.vad.base import VoiceActivityModel
from callback_voice.recording.call_recorder import CallRecorder
from callback_voice.recording.event_log import EventLog
from callback_voice.transports.base import Transport

DRIFT_WARN_S = 0.1


@dataclass(slots=True)
class CallSetup:
    call_id: str
    spec: CallerSpec
    max_duration_s: float
    transport: Transport
    brain: CallerBrain
    speech: CallerSpeech
    make_vad: Callable[[], VoiceActivityModel]
    stt: SpeechToText | None = None
    processors: tuple[ChaosProcessor, ...] = ()


@dataclass(slots=True)
class CallOutcome:
    call_id: str
    started_at: datetime
    duration_s: float
    end_reason: str
    recorder: CallRecorder
    log: EventLog
    max_lateness_s: float


class CallSession:
    """One simulated call, driven by a 20 ms tick loop.

    Each tick: play out the agent's audio, follow its turns, let chaos act, produce
    the caller's frame, shape it (noise, loss, jitter), send it and record both
    channels at the same tick index. Implements ``ChaosContext`` for processors.
    """

    def __init__(self, setup: CallSetup) -> None:
        self._s = setup
        self._clock = TickClock()
        self._playout = PlayoutBuffer()
        self._listener = AgentListener(setup.make_vad())
        self._recorder = CallRecorder()
        self._log = EventLog()
        self._voice = CallerVoice(self._utterance_done)
        self._conversation = Conversation(
            ctx=self,
            spec=setup.spec,
            brain=setup.brain,
            speech=setup.speech,
            voice=self._voice,
            agent_audio=self._recorder.agent,
            processors=list(setup.processors),
            stt=setup.stt,
            log=self._log,
        )

    # --- ChaosContext -------------------------------------------------------------
    @property
    def t_s(self) -> float:
        return self._clock.t_s

    @property
    def tick(self) -> int:
        return self._clock.tick

    @property
    def agent_turn_start_s(self) -> float:
        return self._listener.turn_start_s

    @property
    def agent_turn(self) -> int:
        return self._listener.turn

    @property
    def agent_in_turn(self) -> bool:
        return self._listener.in_turn

    @property
    def agent_speaking(self) -> bool:
        return self._listener.speaking

    @property
    def elapsed_in_agent_turn(self) -> float:
        return self._listener.elapsed_in_turn(self._clock.t_s)

    @property
    def caller_speaking(self) -> bool:
        return self._voice.speaking

    def interject(
        self, audio: Audio, text: str, tag: UtteranceTag, event: ChaosEvent, intended_s: float
    ) -> None:
        self._voice.say(
            Utterance(audio, text, tag, event.id, event.type, intended_s), interrupt=True
        )

    def note(self, event: ChaosEvent, t_s: float, **data: object) -> None:
        self._log.add(t_s, "chaos", chaos_id=event.id, chaos_type=event.type, data=dict(data))

    # --- the call -----------------------------------------------------------------
    async def run(self) -> CallOutcome:
        for processor in self._s.processors:
            await processor.prepare(self._s.speech)
        started_at = datetime.now(UTC)
        await self._s.transport.connect(self._s.call_id)
        self._clock.start()
        self._log.add(0.0, "call_start", data={"transport": self._s.transport.name})
        self._conversation.start()
        try:
            reason = await self._loop()
        finally:
            self._conversation.cancel()
            with contextlib.suppress(Exception):
                await self._s.transport.hangup()
        duration = self._clock.t_s
        if self._clock.max_lateness_s > DRIFT_WARN_S:
            self._log.add(
                duration, "clock_drift", data={"max_lateness_s": self._clock.max_lateness_s}
            )
        self._log.add(duration, "call_end", text=reason)
        return CallOutcome(
            self._s.call_id,
            started_at,
            duration,
            reason,
            self._recorder,
            self._log,
            self._clock.max_lateness_s,
        )

    async def _loop(self) -> str:
        transport = self._s.transport
        while True:
            t = self._clock.t_s
            if transport.closed.is_set():
                return transport.close_reason or "agent_hangup"
            if t >= self._s.max_duration_s:
                return "max_duration"
            if self._conversation.error is not None:
                error = self._conversation.error
                if isinstance(error, CallbackError):
                    raise error
                raise RuntimeError(f"caller failed mid-call: {error!r}") from error
            hang_up_at = self._conversation.hang_up_at
            if hang_up_at is not None and t >= hang_up_at and not self._voice.busy:
                return "caller_hangup"

            for chunk in transport.drain():
                self._playout.push(chunk)
            heard = self._playout.pop_frame()
            for event in self._listener.hear(heard):
                self._on_listener(event)
            self._conversation.tick(t, self._listener.speaking or self._listener.in_turn)
            for processor in self._s.processors:
                processor.on_tick(self)

            clean = self._voice.next_frame(t)
            wire = clean
            for processor in self._s.processors:
                wire = processor.shape_outbound(self, wire)
            await transport.send_audio(wire)
            self._recorder.record_tick(
                self._clock.tick, caller_wire=wire, caller_clean=clean, agent_heard=heard
            )
            await self._clock.next()

    def _on_listener(self, event: AgentTurnStarted | AgentTurnEnded) -> None:
        if isinstance(event, AgentTurnStarted):
            self._log.add(event.t_s, "agent_turn_start", data={"turn": event.turn})
            self._conversation.on_agent_turn_started()
        else:
            self._conversation.on_agent_turn_ended(event)

    def _utterance_done(self, utterance: Utterance, start_s: float, end_s: float) -> None:
        data: dict[str, object] = {"tag": utterance.tag, **utterance.data}
        self._log.add(
            start_s,
            "caller_utterance",
            end_s=round(end_s, 4),
            text=utterance.text,
            chaos_id=utterance.chaos_id,
            chaos_type=utterance.chaos_type,
            intended_s=utterance.intended_s,
            data=data,
        )
        if utterance.takes_floor:
            self._listener.caller_took_floor()
        if utterance.tag not in {"line", "backchannel", "dtmf"} and utterance.text:
            self._s.brain.note_interjection(utterance.text)
        self._conversation.on_utterance_done(utterance, end_s)
