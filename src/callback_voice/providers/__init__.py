"""Swappable model providers (VAD, STT, TTS, LLM). Local implementations come first.

Each interface lives in ``<kind>/base.py``; each implementation is one module; each
``build_<kind>.py`` maps a ``ProviderChoice`` from callback.yaml to an instance.
Optional dependencies are imported lazily inside implementations so the core
install never needs them.
"""
