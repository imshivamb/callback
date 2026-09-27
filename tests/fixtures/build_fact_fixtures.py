"""Build the fact-checking fixtures: one agent read-back heard two ways.

- ``masked-code``: the agent says "D, X, 7, Q, 2" but the "D" is buried in a noise
  burst, the way a bad line swallows a sound. Speech recognition then writes "the X7
  Q2": a transcription loss, not an agent error. Expected verdict: uncertain, review.
- ``garbled-code``: the agent says "B, X, 7, Q, 2". Expected verdict: wrong.

Both read back party size, time and phone correctly. Re-run after changing:

    uv run python tests/fixtures/build_fact_fixtures.py
"""

import asyncio
import json
from pathlib import Path

import numpy as np

from callback_voice.audio.format import SAMPLE_RATE
from callback_voice.audio.normalize_loudness import normalize_loudness
from callback_voice.audio.wav import write_wav
from callback_voice.providers.stt.faster_whisper_stt import FasterWhisperStt
from callback_voice.providers.tts.kokoro_tts import KokoroTts

HERE = Path(__file__).parent / "facts"
LINE = (
    "Done. Your table for 4 is now on Saturday at 7:30 PM. Your reference is still {code}. "
    "I'll text a confirmation to 9 8 1 0 0, 1 2 3 4 5."
)
MASK_S = 0.25


def save(name: str, agent: np.ndarray, truth: dict) -> None:
    lead = np.zeros(SAMPLE_RATE // 2, np.float32)
    agent = np.concatenate([lead, agent, lead])
    silent = np.zeros_like(agent)
    out = HERE / name
    write_wav(out / "call.wav", np.stack([silent, agent], axis=1))
    write_wav(out / "caller_clean.wav", silent)
    (out / "events.jsonl").write_text(json.dumps({"t_s": 0.0, "kind": "call_start"}) + "\n")
    (out / "truth.json").write_text(json.dumps(truth, indent=2) + "\n")


async def main() -> None:
    tts = KokoroTts("af_heart")
    correct = normalize_loudness(await tts.synthesize(LINE.format(code="D, X, 7, Q, 2")))
    garbled = normalize_loudness(await tts.synthesize(LINE.format(code="B, X, 7, Q, 2")))

    words = (await FasterWhisperStt("small", words=True).transcribe(correct, language="en")).words
    code = next(w for w in words if "X7" in w.text.upper().replace(" ", ""))
    start = int(code.start_s * SAMPLE_RATE)
    masked = correct.copy()
    noise = np.random.default_rng(1).normal(0, 0.1, int(MASK_S * SAMPLE_RATE)).astype(np.float32)
    masked[start : start + noise.size] = masked[start : start + noise.size] * 0.1 + noise

    shared = {
        "count 4 people": "correct",
        "time 7:30 PM": "correct",
        "phone 98100 12345": "correct",
    }
    save("masked-code", masked, {"code DX7Q2": "uncertain", **shared})
    save("garbled-code", garbled, {"code DX7Q2": "wrong", **shared})


if __name__ == "__main__":
    asyncio.run(main())
