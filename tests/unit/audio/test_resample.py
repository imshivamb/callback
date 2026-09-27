import numpy as np
import pytest

from callback_voice.audio.resample import resample


@pytest.mark.parametrize(
    ("src", "dst"), [(24_000, 16_000), (8_000, 16_000), (16_000, 8_000), (44_100, 16_000)]
)
def test_length_and_tone_preserved(src: int, dst: int) -> None:
    seconds = 0.5
    t = np.arange(int(src * seconds)) / src
    tone = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    out = resample(tone, src, dst)
    assert abs(out.size - dst * seconds) <= 1
    spectrum = np.abs(np.fft.rfft(out[200:-200] * np.hanning(out.size - 400)))
    peak_hz = np.argmax(spectrum) * dst / (out.size - 400)
    assert abs(peak_hz - 440) < 8
    assert 0.6 < np.max(np.abs(out[200:-200])) < 1.1


def test_identity_when_rates_match() -> None:
    audio = np.ones(10, dtype=np.float32)
    assert resample(audio, 16_000, 16_000) is not None
    assert np.array_equal(resample(audio, 16_000, 16_000), audio)
