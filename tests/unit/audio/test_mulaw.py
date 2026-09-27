import numpy as np

from callback_voice.audio.mulaw import mulaw_decode, mulaw_encode


def test_roundtrip_error_is_logarithmic() -> None:
    audio = (np.sin(np.linspace(0, 40 * np.pi, 8000)) * 0.5).astype(np.float32)
    back = mulaw_decode(mulaw_encode(audio))
    assert back.size == audio.size
    snr = 10 * np.log10(np.sum(audio**2) / np.sum((audio - back) ** 2))
    assert snr > 30


def test_silence_encodes_to_0xff() -> None:
    assert mulaw_encode(np.zeros(4, dtype=np.float32)) == b"\xff" * 4
