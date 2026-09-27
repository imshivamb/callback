import numpy as np
import pytest

from callback_voice.audio.dtmf import dtmf_tones
from callback_voice.audio.format import SAMPLE_RATE


def test_digit_has_its_two_frequencies() -> None:
    tone = dtmf_tones("5", tone_s=0.2, gap_s=0.0)
    spectrum = np.abs(np.fft.rfft(tone))
    freqs = np.fft.rfftfreq(tone.size, 1 / SAMPLE_RATE)
    top = sorted(freqs[np.argsort(spectrum)[-2:]])
    assert abs(top[0] - 770) < 10 and abs(top[1] - 1336) < 10


def test_rejects_non_digit() -> None:
    with pytest.raises(ValueError):
        dtmf_tones("x")
