import asyncio
import contextlib
import logging
import time
from collections.abc import Coroutine
from dataclasses import dataclass

from websockets.exceptions import ConnectionClosed

from callback_voice.audio.format import Audio
from callback_voice.audio.pcm import from_pcm16
from callback_voice.audio.tape import AudioTape
from callback_voice.providers.stt.base import SpeechToText, Transcript
from callback_voice.providers.tts.base import TextToSpeech
from callback_voice.providers.vad.base import VoiceActivityModel
from callback_voice.providers.vad.speech_detector import SpeechDetector
from callback_voice.reference_agents.restaurant.dialog.reply import Reply
from callback_voice.reference_agents.restaurant.dialog.reservation_brain import ReservationBrain
from callback_voice.reference_agents.restaurant.voice.behavior import AgentBehavior
from callback_voice.reference_agents.restaurant.voice.call_line import CallLine
from callback_voice.reference_agents.restaurant.voice.caller_turn_tracker import CallerTurnTracker
from callback_voice.reference_agents.restaurant.voice.interruption_policy import (
    interruption_decision,
)
from callback_voice.reference_agents.restaurant.voice.is_backchannel import is_backchannel
from callback_voice.reference_agents.restaurant.voice.paced_speaker import PacedSpeaker
from callback_voice.reference_agents.restaurant.voice.sounds_like_interruption import (
    sounds_like_interruption,
)
from callback_voice.reference_agents.restaurant.voice.speech_chunks import speech_chunks
from callback_voice.reference_agents.restaurant.voice.split_sentences import split_sentences

log = logging.getLogger("callback.reference_agent")
_PRE_ROLL_S = 0.15
_LONG_RUN_S = 0.9
_CONFIRM_STAGES = frozenset({"confirm_move", "confirm_cancel", "confirm_new", "choose_slot"})


@dataclass(slots=True)
class AgentModels:
    stt: SpeechToText
    judge_stt: SpeechToText
    """A small, fast model for deciding mid-sentence whether the caller is only backchanneling."""
    tts: TextToSpeech
    vad: VoiceActivityModel


class AgentSession:
    """One phone call with the restaurant agent: listen, decide, speak, yield."""

    def __init__(
        self,
        line: CallLine,
        behavior: AgentBehavior,
        models: AgentModels,
        brain: ReservationBrain,
    ) -> None:
        self._line = line
        self._behavior = behavior
        self._m = models
        self._brain = brain
        self._detector = SpeechDetector(models.vad)
        self._tape = AudioTape()
        self._turns = CallerTurnTracker(behavior.end_of_turn_silence_s)
        self._speaker = PacedSpeaker(self._send)
        self._reply_task: asyncio.Task[None] | None = None
        self._judge_task: asyncio.Task[None] | None = None
        self._judged_backchannel = False
        self._last_activity = time.monotonic()
        self._hanging_up = False
        self._timing: dict[str, float] = {}
        # Transcription started as soon as the caller went quiet, keyed by the turn span.
        self._early: tuple[tuple[float, float], asyncio.Task[Transcript]] | None = None

    async def run(self) -> None:
        speaker = asyncio.create_task(self._speaker.run())
        watcher = asyncio.create_task(self._watch_silence())
        self._start_reply(self._speak(self._brain.greet()))
        try:
            async for message in self._line:
                if isinstance(message, bytes):
                    await self._on_audio(message)
                elif '"hangup"' in message:
                    break
        except ConnectionClosed:
            pass
        finally:
            for task in (speaker, watcher, self._reply_task, self._judge_task):
                if task is not None:
                    task.cancel()

    async def _on_audio(self, message: bytes) -> None:
        audio = from_pcm16(message)
        self._tape.append(audio)
        for edge in self._detector.push(audio):
            if edge.kind == "start":
                self._on_caller_start(edge.t_s)
            else:
                self._turns.on_speech_end(edge.t_s)
                self._judged_backchannel = False
                self._transcribe_early()
        if self._detector.speaking:
            self._last_activity = time.monotonic()
            if self._holding_floor:
                self._consider_yield()
            elif (
                self._turns.run_kind != "turn"
                and self._detector.speech_duration_s >= _LONG_RUN_S
                and not (self._behavior.barge_in == "ignore" and self._turns.run_kind == "unheard")
            ):
                self._turns.promote_run()  # kept talking after we finished: a real turn
        span = self._turns.turn_complete(self._detector.now_s, self._detector.speaking)
        if span is not None:
            clip = self._tape.slice(span[0] - _PRE_ROLL_S, span[1] + 0.1)
            early = self._early[1] if self._early is not None and self._early[0] == span else None
            self._early = None
            self._start_reply(self._answer(clip, early))

    def _on_caller_start(self, t_s: float) -> None:
        if self._holding_floor:
            deaf = self._behavior.barge_in == "ignore" or (
                self._behavior.barge_in == "deaf_opening"
                and self._speaker.reply_played_s < self._behavior.deaf_opening_s
            )
            self._turns.on_speech_start(t_s, "unheard" if deaf else "ignored")
            return
        if self._reply_task and not self._reply_task.done() and not self._hanging_up:
            self._reply_task.cancel()  # caller kept talking while we were thinking
        self._turns.on_speech_start(t_s, "turn")

    def _consider_yield(self) -> None:
        decision = interruption_decision(
            self._behavior,
            speech_s=self._detector.speech_duration_s,
            reply_played_s=self._speaker.reply_played_s,
            judged_backchannel=self._judged_backchannel,
        )
        if decision == "yield" and not self._speaker.stopping:  # log a delayed stop once
            log.info("yield: caller spoke for %.2f s", self._detector.speech_duration_s)
            self._yield()
        elif decision == "judge" and self._judge_task is None:
            clip = self._tape.slice(self._turns.run_start - _PRE_ROLL_S, self._detector.now_s)
            self._judge_task = asyncio.create_task(self._judge(clip))

    async def _judge(self, clip: Audio) -> None:
        try:
            transcript = await self._m.judge_stt.transcribe(clip, language="en")
            if not sounds_like_interruption(transcript.text) or is_backchannel(transcript.text):
                self._judged_backchannel = True
                log.info(
                    "judged %r a backchannel after %.2f s",
                    transcript.text,
                    self._detector.speech_duration_s,
                )
                log.info("ignored backchannel %r", transcript.text)
            elif self._holding_floor:
                log.info("not a backchannel: %r", transcript.text)
                self._yield()
        finally:
            self._judge_task = None

    @property
    def _holding_floor(self) -> bool:
        """Speaking, or mid-reply between sentences while the next one is synthesised.

        Without the second half, a "mm-hmm" in a synthesis gap would look like a new
        caller turn and cancel the rest of the reply.
        """
        replying = self._reply_task is not None and not self._reply_task.done()
        return self._speaker.busy or (replying and self._speaker.sentence_index >= 0)

    def _yield(self) -> None:
        if self._hanging_up or self._speaker.stopping:
            return
        log.info("caller barged in; yielding (sentence %d)", self._speaker.sentence_index)
        self._speaker.stop(after_s=self._behavior.stop_lag_s)
        if self._reply_task and not self._reply_task.done():
            self._reply_task.cancel()
        self._turns.promote_run()

    def _transcribe_early(self) -> None:
        """Start transcribing the moment the caller goes quiet, during the end-of-turn
        wait, so the words are ready when the turn is confirmed. If the caller speaks
        again, the turn's span changes and this result is simply not used."""
        start, end = self._turns.turn_start, self._turns.pending_end
        if start is None or end is None:
            return
        if self._early is not None:
            self._early[1].cancel()
        clip = self._tape.slice(start - _PRE_ROLL_S, end + 0.1)
        self._early = (
            (start, end),
            asyncio.create_task(self._m.stt.transcribe(clip, language="en")),
        )

    async def _answer(self, clip: Audio, early: "asyncio.Task[Transcript] | None" = None) -> None:
        began = time.monotonic()
        if early is not None and not early.cancelled():
            transcript = await early  # usually already done: the wait hid the transcription
        else:
            transcript = await self._m.stt.transcribe(clip, language="en")
        self._timing = {"stt": time.monotonic() - began, "early": 1.0 if early else 0.0}
        text = transcript.text.strip()
        log.info("caller: %s", text)
        # "okay" answers a yes/no question; anywhere else a lone backchannel needs no reply.
        if not text or (is_backchannel(text) and self._brain.state.stage not in _CONFIRM_STAGES):
            return
        reply = self._brain.respond(text)
        await asyncio.sleep(self._behavior.think_delay_s)
        await self._speak(reply)

    async def _synthesize(self, text: str) -> Audio:
        if self._behavior.synthesis_delay_s:
            await asyncio.sleep(self._behavior.synthesis_delay_s)
        return await self._m.tts.synthesize(text, voice=self._behavior.voice)

    def _log_timing(self, tts_first: float) -> None:
        if self._timing:
            self._timing["tts_first"] = tts_first
            log.info("timing: %s", " ".join(f"{k}={v:.2f}s" for k, v in self._timing.items()))
            self._timing = {}

    async def _speak(self, reply: Reply) -> None:
        log.info("agent: %s", reply.text)
        self._speaker.begin_reply()
        # Only the good agent opens with a short chunk; the buggy agent keeps its
        # original sentence timing (see F52 in the history of this choice).
        chunks = (
            speech_chunks(reply.text)
            if self._behavior.barge_in == "smart"
            else split_sentences(reply.text)
        )
        if self._behavior.barge_in == "ignore":
            # Talks straight through, with no pauses for synthesis that could look like
            # it stopped to listen: render the whole reply before the first word.
            began = time.monotonic()
            audios = [await self._synthesize(c) for c in chunks]
            self._log_timing(time.monotonic() - began)
            for audio in audios:
                self._speaker.enqueue(audio)
        else:
            for i, chunk in enumerate(chunks):
                began = time.monotonic()
                audio = await self._synthesize(chunk)
                if i == 0:
                    self._log_timing(time.monotonic() - began)
                self._speaker.enqueue(audio)
        if reply.end_call:
            self._hanging_up = True
            await self._speaker.idle.wait()
            await asyncio.sleep(0.4)
            await self._line.close()

    def _start_reply(self, work: Coroutine[None, None, None]) -> None:
        if self._reply_task and not self._reply_task.done():
            self._reply_task.cancel()
        self._reply_task = asyncio.create_task(work)

    async def _watch_silence(self) -> None:
        """Reprompt a caller who has gone quiet (good agent only)."""
        limit = self._behavior.reprompt_after_s
        while limit is not None:
            await asyncio.sleep(0.2)
            idle_since = max(self._last_activity, self._speaker.last_spoke_at)
            busy = (
                self._speaker.busy
                or self._turns.mid_turn
                or self._detector.speaking
                or (self._reply_task is not None and not self._reply_task.done())
            )
            if not busy and time.monotonic() - idle_since >= limit:
                self._last_activity = time.monotonic()
                self._start_reply(self._speak(self._brain.reprompt()))

    async def _send(self, frame: bytes) -> None:
        with contextlib.suppress(ConnectionClosed):
            await self._line.send(frame)
