import numpy as np

from callback_voice.audio.format import FRAME_SAMPLES, SAMPLE_RATE
from callback_voice.audio.resample import resample
from callback_voice.audio.stream_resampler import StreamResampler
from callback_voice.caller.engine.agent_listener import (
    AgentListener,
    AgentTurnEnded,
    AgentTurnStarted,
)
from callback_voice.caller.engine.caller_voice import CallerVoice
from callback_voice.caller.engine.playout_buffer import PlayoutBuffer
from callback_voice.caller.engine.utterance import Utterance
from callback_voice.providers.vad.energy_vad import EnergyVad


def tone(seconds: float) -> np.ndarray:
    t = np.arange(round(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    return (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


def test_playout_paces_bursts_and_fills_gaps() -> None:
    buffer = PlayoutBuffer()
    buffer.push(np.ones(FRAME_SAMPLES * 3 + 10, np.float32))
    frames = [buffer.pop_frame() for _ in range(5)]
    assert [float(f.mean()) for f in frames[:3]] == [1.0, 1.0, 1.0]
    assert frames[3][:10].sum() == 10 and frames[3][10:].sum() == 0
    assert frames[4].sum() == 0


def test_voice_reports_timing_and_preempts() -> None:
    done: list[tuple[str, float, float]] = []
    voice = CallerVoice(lambda u, s, e: done.append((u.text, s, e)))
    voice.say(Utterance(tone(0.1), "line", lead_silence_s=0.04))
    for tick in range(4):
        voice.next_frame(tick * 0.02)
    voice.say(Utterance(tone(0.04), "hmm", "backchannel"), interrupt=True)
    for tick in range(4, 8):
        voice.next_frame(tick * 0.02)
    (text1, s1, e1), (text2, s2, e2) = done
    assert (text1, s1) == ("line", 0.04) and abs(e1 - 0.08) < 1e-9
    assert text2 == "hmm" and abs(s2 - 0.08) < 1e-9 and abs(e2 - 0.12) < 1e-9


def test_listener_numbers_turns_and_endpoints() -> None:
    listener = AgentListener(EnergyVad(), endpoint_s=0.5)
    audio = np.concatenate(
        [tone(1.0), np.zeros(SAMPLE_RATE, np.float32), tone(0.6), np.zeros(SAMPLE_RATE, np.float32)]
    )
    events = []
    for i in range(0, audio.size, FRAME_SAMPLES):
        events += listener.hear(audio[i : i + FRAME_SAMPLES])
        if i == 2 * SAMPLE_RATE - FRAME_SAMPLES:
            listener.caller_took_floor()
    started = [e for e in events if isinstance(e, AgentTurnStarted)]
    ended = [e for e in events if isinstance(e, AgentTurnEnded)]
    assert [e.turn for e in started] == [1, 2]
    assert abs(ended[0].end_s - 1.0) < 0.05 and abs(started[1].t_s - 2.0) < 0.05


def test_stream_resampler_matches_batch() -> None:
    x = tone(0.5)
    r = StreamResampler(16_000, 8_000)
    out = np.concatenate([r.process(x[i : i + 333]) for i in range(0, x.size, 333)])
    ref = resample(x, 16_000, 8_000)
    assert np.allclose(out[100:3000], ref[100:3000], atol=1e-6)
