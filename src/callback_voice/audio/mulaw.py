"""G.711 mu-law codec for telephone transports (Twilio Media Streams)."""

import numpy as np

from callback_voice.audio.format import Audio

_BIAS = 0x84
_CLIP = 32635


def mulaw_encode(audio: Audio) -> bytes:
    """Encode float audio to 8-bit G.711 mu-law."""
    pcm = (np.clip(audio, -1.0, 1.0) * 32767.0).astype(np.int32)
    sign = np.where(pcm < 0, 0x80, 0x00)
    magnitude = np.minimum(np.abs(pcm), _CLIP) + _BIAS
    exponent = np.floor(np.log2(magnitude)).astype(np.int32) - 7
    exponent = np.clip(exponent, 0, 7)
    mantissa = (magnitude >> (exponent + 3)) & 0x0F
    encoded = ~(sign | (exponent << 4) | mantissa) & 0xFF
    return bytes(encoded.astype(np.uint8).tobytes())


def mulaw_decode(data: bytes) -> Audio:
    """Decode 8-bit G.711 mu-law to float audio."""
    codes = ~np.frombuffer(data, dtype=np.uint8).astype(np.int32) & 0xFF
    sign = codes & 0x80
    exponent = (codes >> 4) & 0x07
    mantissa = codes & 0x0F
    magnitude = (((mantissa << 3) + _BIAS) << exponent) - _BIAS
    pcm = np.where(sign != 0, -magnitude, magnitude)
    return (pcm.astype(np.float32) / 32768.0).astype(np.float32)
