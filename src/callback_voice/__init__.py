"""Callback: chaos testing for voice agents.

Real calls, real audio, one exit code.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("callback-voice")
except PackageNotFoundError:  # running from a source checkout without install
    __version__ = "0.0.0+local"

__all__ = ["__version__"]
