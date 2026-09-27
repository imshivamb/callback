"""Audio primitives shared by the caller, the recorder, the scorer and reference agents.

Internally all audio is mono float32 in [-1, 1] at ``SAMPLE_RATE``. PCM16 only exists
at the transport boundary.
"""
