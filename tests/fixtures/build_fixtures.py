"""Build synthetic calls with known timings for scorer accuracy tests.

Real Kokoro speech is placed on each channel at exact sample positions, so true
speech edges are known to the sample. Truth is written next to each call in
``truth.json``. Re-run after changing a fixture (name some to rebuild only those):

    uv run python tests/fixtures/build_fixtures.py [unanswered ...]
"""

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from callback_voice.audio.format import SAMPLE_RATE, Audio
from callback_voice.audio.normalize_loudness import normalize_loudness
from callback_voice.audio.wav import write_wav
from callback_voice.providers.tts.kokoro_tts import KokoroTts

HERE = Path(__file__).parent / "calls"
ONLY: set[str] | None = None  # set from the command line: build only these fixtures
_WINDOW = SAMPLE_RATE // 100


def speech_edges(clip: Audio) -> tuple[float, float]:
    """First and last 10 ms window louder than -40 dBFS: the clip's true speech span."""
    frames = clip[: clip.size // _WINDOW * _WINDOW].reshape(-1, _WINDOW)
    loud = np.flatnonzero(10 * np.log10(np.mean(frames**2, axis=1) + 1e-12) > -40)
    return loud[0] * _WINDOW / SAMPLE_RATE, (loud[-1] + 1) * _WINDOW / SAMPLE_RATE


@dataclass
class Call:
    name: str
    agent: np.ndarray = field(default_factory=lambda: np.zeros(SAMPLE_RATE * 40, np.float32))
    caller: np.ndarray = field(default_factory=lambda: np.zeros(SAMPLE_RATE * 40, np.float32))
    events: list[dict] = field(default_factory=list)
    truth: dict = field(default_factory=dict)
    end_s: float = 0.0

    def place(self, channel: str, clip: Audio, at_s: float) -> tuple[float, float]:
        """Place ``clip`` so its speech starts at ``at_s``; return true speech (start, end)."""
        on, off = speech_edges(clip)
        start = round((at_s - on) * SAMPLE_RATE)
        getattr(self, channel)[start : start + clip.size] += clip
        self.end_s = max(self.end_s, at_s + (off - on) + 1.0)
        return at_s, at_s + (off - on)

    def say(self, clip: Audio, text: str, at_s: float, tag: str = "line") -> tuple[float, float]:
        on, off = self.place("caller", clip, at_s)
        self.events.append(
            {
                "t_s": round(on - 0.03, 4),
                "kind": "caller_utterance",
                "end_s": round(off + 0.03, 4),
                "text": text,
                "data": {"tag": tag},
            }
        )
        return on, off

    def save(self) -> None:
        if ONLY is not None and self.name not in ONLY:
            return
        out = HERE / self.name
        n = round(self.end_s * SAMPLE_RATE)
        write_wav(out / "call.wav", np.stack([self.caller[:n], self.agent[:n]], axis=1))
        write_wav(out / "caller_clean.wav", self.caller[:n])
        (out / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in self.events))
        (out / "truth.json").write_text(json.dumps(self.truth, indent=2) + "\n")


async def main() -> None:
    """Build every fixture, or only those named on the command line (``ONLY``)."""
    agent_tts, caller_tts = KokoroTts("af_heart"), KokoroTts("am_michael")

    async def a(text: str) -> Audio:
        return normalize_loudness(await agent_tts.synthesize(text))

    async def c(text: str) -> Audio:
        return normalize_loudness(await caller_tts.synthesize(text))

    greeting = await a("Thanks for calling Olive and Ember. How can I help you today?")
    reply = await a("Sure, I can help with that. What's the booking reference?")
    long_reply = await a(
        "I found your booking. It's a table for four this Friday at eight in the "
        "evening, and I can move it to any evening this week."
    )
    short = await a("Great, that's done.")

    # 1. Plain turn-taking with three known response latencies.
    call = Call("turn_taking")
    _, g_end = call.place("agent", greeting, 0.5)
    lines = ["Hi, I need to move my booking.", "It's D X 7 Q 2.", "Saturday at seven, please."]
    latencies = [0.45, 1.2, 2.1]
    t = g_end + 0.7
    agent_clips = [reply, long_reply, short]
    for line, latency, agent_clip in zip(lines, latencies, agent_clips, strict=True):
        _, c_end = call.say(await c(line), line, t)
        _, a_end = call.place("agent", agent_clip, c_end + latency)
        t = a_end + 0.7
    call.truth = {"response_latencies_s": latencies, "time_to_yield_s": [], "talk_over_ratio": 0.0}
    call.save()

    # 2. Barge-in the agent yields to after 0.35 s.
    call = Call("barge_in_yield")
    a_on, _ = call.place("agent", long_reply, 0.5)
    t = a_on + 2.0
    barge = await c("Sorry, I just need to move my booking.")
    b_on, b_end = call.say(barge, "Sorry, I just need to move my booking.", t, tag="barge_in")
    call.agent[round((b_on + 0.35) * SAMPLE_RATE) :] = 0  # the agent stops mid-word
    call.place("agent", reply, b_end + 0.8)
    call.truth = {"response_latencies_s": [0.8], "time_to_yield_s": [0.35], "talk_over_ratio": 0.0}
    call.save()

    # 3. Barge-in the agent ignores: it talks straight over the caller.
    call = Call("barge_in_ignored")
    a_on, a_end = call.place("agent", long_reply, 0.5)
    barge = await c("Wait, wait, not Friday.")
    b_on, b_end = call.say(barge, "Wait, wait, not Friday.", a_on + 1.5, tag="barge_in")
    overlap_after_grace = max(0.0, min(a_end, b_end) - (b_on + 0.6))
    call.truth = {
        "response_latencies_s": [],
        "time_to_yield_s": [round(a_end - b_on, 3)],
        "talk_over_ratio": round(overlap_after_grace / (b_end - b_on - 0.6), 4),
    }
    call.save()

    # 4. Noisy line: the caller's wire channel carries a noise bed, the clean stem does not.
    call = Call("noisy_line")
    _, g_end = call.place("agent", greeting, 0.5)
    _, c_end = call.say(
        await c("Hi, I need to move my booking."), "Hi, I need to move my booking.", g_end + 0.7
    )
    call.place("agent", reply, c_end + 0.9)
    rng = np.random.default_rng(7)
    noise = rng.normal(0, 0.03, call.caller.size).astype(np.float32)
    clean = call.caller.copy()
    call.caller = clean + noise
    call.truth = {"response_latencies_s": [0.9], "time_to_yield_s": [], "talk_over_ratio": 0.0}
    call.save()
    if ONLY is None or "noisy_line" in ONLY:
        write_wav(
            HERE / "noisy_line" / "caller_clean.wav", clean[: round(call.end_s * SAMPLE_RATE)]
        )

    # 5. An unanswered turn: the caller asks, waits 3 s in silence, and has to ask again.
    #    Then two lines back to back (0.15 s apart): the agent had no opening after the
    #    first, so that one is not an unanswered turn.
    call = Call("unanswered")
    _, g_end = call.place("agent", greeting, 0.5)
    ask = "Hi, I need to move my booking."
    _, c_end = call.say(await c(ask), ask, g_end + 0.7)
    _, a_end = call.place("agent", reply, c_end + 0.8)
    ignored = "It's D X 7 Q 2."
    _, i_end = call.say(await c(ignored), ignored, a_end + 0.7)
    again = "Hello? Are you there?"
    _, again_end = call.say(await c(again), again, i_end + 3.0)
    _, a_end = call.place("agent", short, again_end + 0.9)
    first, second = "Saturday works.", "Seven thirty, please."
    _, f_end = call.say(await c(first), first, a_end + 0.7)
    _, s_end = call.say(await c(second), second, f_end + 0.15)
    call.place("agent", short, s_end + 0.8)
    call.truth = {
        "response_latencies_s": [0.8, 0.9, 0.8],
        "time_to_yield_s": [],
        "talk_over_ratio": 0.0,
        "unanswered_turns": [{"t_s": round(i_end, 3), "waited_s": 3.0, "text": ignored}],
    }
    call.save()


if __name__ == "__main__":
    import sys

    ONLY = set(sys.argv[1:]) or None
    asyncio.run(main())
