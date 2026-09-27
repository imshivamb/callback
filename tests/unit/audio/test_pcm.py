import numpy as np

from callback_voice.audio.pcm import from_pcm16, to_pcm16


def test_roundtrip_is_within_one_lsb() -> None:
    audio = np.linspace(-1, 1, 1001, dtype=np.float32)
    back = from_pcm16(to_pcm16(audio))
    assert np.max(np.abs(back - audio)) < 2 / 32768


def test_clips_out_of_range_values() -> None:
    back = from_pcm16(to_pcm16(np.array([2.0, -2.0], dtype=np.float32)))
    assert back[0] > 0.999 and back[1] < -0.999


def test_ignores_trailing_odd_byte() -> None:
    assert from_pcm16(b"\x00\x40\x01").size == 1
