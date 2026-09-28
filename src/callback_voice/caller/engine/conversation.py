import asyncio
import contextlib
import time

import numpy as np

from callback_voice.audio.dtmf import dtmf_tones
from callback_voice.audio.tape import AudioTape
from callback_voice.caller.brain.base import CallerBrain
from callback_voice.caller.engine.agent_listener import AgentTurnEnded
from callback_voice.caller.engine.caller_voice import CallerVoice
from callback_voice.caller.engine.utterance import Utterance
from callback_voice.caller.speech.caller_speech import CallerSpeech
from callback_voice.chaos.processors.chaos_context import ChaosContext
from callback_voice.chaos.processors.chaos_processor import ChaosProcessor
from callback_voice.chaos.processors.line_plan import LinePlan
from callback_voice.core.models.caller_spec import CallerSpec
from callback_voice.providers.stt.base import SpeechToText
from callback_voice.recording.event_log import EventLog

_FIRST_NUDGE_S = 5.0
_NUDGE_S = 12.0
_MAX_NUDGES = 2
_GOODBYE_WAIT_S = 4.0
_AFTER_GOODBYE_S = 0.4
_REPLY_TO_BARGE_IN_S = 2.5
"""After cutting in, how long a caller waits in silence for the agent to respond before
going on. Longer than the default reply-delay limit (1.5 s), so an agent that ignores
the interruption is still counted as leaving the caller unanswered."""


class Conversation:
    """Turn-taking for the simulated caller.

    When the agent finishes a turn the caller transcribes it (only if the brain needs
    the words), asks the brain for a line, lets chaos rewrite it, renders it and
    queues it. If the agent resumes before the line starts, the plan is dropped and
    re-made when the agent is done. After a barge-in the caller waits for the agent
    to respond to it rather than answering the turn it interrupted straight away.
    Also nudges an agent that goes silent, and hangs up once the caller's goal is done
    and the agent has said goodbye.
    """

    def __init__(
        self,
        *,
        ctx: ChaosContext,
        spec: CallerSpec,
        brain: CallerBrain,
        speech: CallerSpeech,
        voice: CallerVoice,
        agent_audio: AudioTape,
        processors: list[ChaosProcessor],
        stt: SpeechToText | None,
        log: EventLog,
    ) -> None:
        self._ctx, self._spec, self._brain, self._speech = ctx, spec, brain, speech
        self._voice, self._agent_audio, self._processors = voice, agent_audio, processors
        self._stt, self._log = stt, log
        self.caller_turn = 0
        self.hang_up_at: float | None = None
        self._task: asyncio.Task[None] | None = None
        self._final: Utterance | None = None
        self._last_floor_end = 0.0
        self._nudges = 0
        self._committed = False
        self._held: Utterance | None = None
        self._barged_in_at: float | None = None  # end of our barge-in, until the agent responds
        self._interrupted: AgentTurnEnded | None = None  # the turn we cut into
        self._timing: dict[str, float] = {}
        self.error: BaseException | None = None

    def start(self) -> None:
        if self._spec.speaks_first:
            self._begin_planning(agent_said_audio=None)

    def on_agent_turn_started(self) -> None:
        # The agent kept going. An undecided plan is dropped and re-made when the agent
        # is done; a line the brain already decided is held and said then instead.
        if self._task is not None and not self._task.done() and not self._committed:
            self._task.cancel()
        if self._barged_in_at is not None:  # the agent is responding to our interruption
            self._barged_in_at, self._interrupted = None, None
        waiting = self._voice.withdraw_if_waiting()
        if waiting is not None:  # the agent reprompted during a deliberate silence
            waiting.lead_silence_s = 0.0
            self._held = waiting

    def on_agent_turn_ended(self, ended: AgentTurnEnded) -> None:
        # A line decided while the agent was still talking goes first, even the goodbye:
        # returning early for a pending goodbye here left it unsaid and the call stuck.
        if self._held is not None:
            held, self._held = self._held, None
            self._voice.say(held)
            return
        if self._final is not None or self.hang_up_at is not None:
            if self._final is None:  # our goodbye is done; the agent answered it
                self.hang_up_at = min(self.hang_up_at or 1e9, self._ctx.t_s + _AFTER_GOODBYE_S)
            return
        current = self._voice.current
        if current is not None and current.tag == "barge_in":
            self._interrupted = ended  # ended under our barge-in; wait once it's done
            return
        if self._voice.busy or (self._task is not None and not self._task.done()):
            return
        if self._barged_in_at is not None and ended.start_s < self._barged_in_at:
            # The turn we cut into: a person waits for the agent to answer the interruption.
            self._interrupted = ended
            return
        self._begin_planning(self._agent_audio.slice(ended.start_s - 0.1, ended.end_s + 0.1))

    def on_utterance_done(self, utterance: Utterance, end_s: float) -> None:
        if utterance.takes_floor:
            self._last_floor_end = end_s
        if utterance.tag == "barge_in":
            self._barged_in_at = end_s
        if utterance is self._final:
            self._final = None
            self.hang_up_at = end_s + _GOODBYE_WAIT_S

    def tick(self, t_s: float, agent_active: bool) -> None:
        """Nudge an agent that has gone quiet, then give up."""
        idle = (
            not self._voice.busy and not agent_active and (self._task is None or self._task.done())
        )
        if not idle or self.hang_up_at is not None or self._final is not None:
            return
        if self._interrupted is not None and self._barged_in_at is not None:
            quiet_since = max(self._barged_in_at, self._interrupted.end_s)
            if t_s - quiet_since >= _REPLY_TO_BARGE_IN_S:
                turn, self._interrupted, self._barged_in_at = self._interrupted, None, None
                self._log.add(t_s, "note", text="no reply to the interruption; caller goes on")
                self._begin_planning(self._agent_audio.slice(turn.start_s - 0.1, turn.end_s + 0.1))
            return
        limit = _FIRST_NUDGE_S if self._ctx.agent_turn == 0 else _NUDGE_S
        if t_s - self._last_floor_end < limit:
            return
        if self._nudges >= _MAX_NUDGES:
            self.hang_up_at = t_s
            self._log.add(t_s, "note", text="agent unresponsive; caller hung up")
            return
        self._nudges += 1
        self._last_floor_end = t_s
        self._task = asyncio.create_task(
            self._say(LinePlan("Hello? Are you still there?", tag="nudge"))
        )

    def cancel(self) -> None:
        if self._task is not None:
            self._task.cancel()

    def _begin_planning(self, agent_said_audio: np.ndarray | None) -> None:
        self._committed = False
        self._task = asyncio.create_task(self._plan(agent_said_audio))
        self._task.add_done_callback(self._record_failure)

    async def _plan(self, agent_audio: np.ndarray | None) -> None:
        began = time.monotonic()
        agent_said = ""
        if agent_audio is not None and self._brain.needs_agent_text and self._stt is not None:
            agent_said = (
                await self._stt.transcribe(agent_audio, language=self._spec.language)
            ).text
            self._log.add(
                self._ctx.t_s,
                "agent_turn_end",
                text=agent_said,
                data={"turn": self._ctx.agent_turn, "stt_s": round(time.monotonic() - began, 3)},
            )
        thinking = time.monotonic()
        line = await self._brain.next_line(agent_said)
        self._committed = True
        self._timing = {"brain_s": round(time.monotonic() - thinking, 3)}
        if line is None:
            self.hang_up_at = self._ctx.t_s
            return
        self.caller_turn += 1
        plan = LinePlan(line.text, hang_up=line.hang_up)
        for processor in self._processors:
            plan = processor.before_caller_turn(self._ctx, self.caller_turn, plan)
        if plan.text != line.text:
            self._brain.revise_last_line(plan.text)
        if plan.updates:
            self._brain.apply_updates(plan.updates)
        await self._say(plan)

    async def _say(self, plan: LinePlan) -> None:
        rendering = time.monotonic()
        audio = await self._speech.render(plan.text) if plan.text else np.zeros(0, np.float32)
        timing = {**self._timing, "tts_s": round(time.monotonic() - rendering, 3)}
        self._timing = {}
        if plan.dtmf:
            audio = np.concatenate([audio, dtmf_tones(plan.dtmf)])
        utterance = Utterance(
            audio,
            plan.text,
            plan.tag,
            plan.chaos_id,
            plan.chaos_type,
            lead_silence_s=plan.lead_silence_s,
        )
        if plan.dtmf:
            utterance.data["dtmf"] = plan.dtmf
        utterance.data["caller_timing"] = timing
        if plan.hang_up:
            self._final = utterance
        if self._ctx.agent_in_turn and plan.tag == "line":
            self._held = utterance  # wait for the agent to finish, then say it
        else:
            self._voice.say(utterance)

    def _record_failure(self, task: asyncio.Task[None]) -> None:
        with contextlib.suppress(asyncio.CancelledError):
            if task.exception() is not None:
                self.error = task.exception()
