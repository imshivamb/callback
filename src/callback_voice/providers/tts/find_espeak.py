import ctypes
import ctypes.util
import os
import subprocess
import sys
from dataclasses import dataclass
from functools import cache
from pathlib import Path

_BREW_PREFIXES = ("/opt/homebrew", "/usr/local")


@dataclass(frozen=True, slots=True)
class EspeakInstall:
    library: str
    data_path: str


@cache
def find_espeak() -> EspeakInstall | None:
    """Locate a working espeak-ng shared library and its data directory.

    A system install is preferred: the library bundled by ``espeakng-loader`` on
    macOS arm64 ignores the data path it is given. ``PHONEMIZER_ESPEAK_LIBRARY`` and
    ``ESPEAK_DATA_PATH`` override detection.
    """
    for library in _candidate_libraries():
        data = _data_path_for(library)
        if data is not None and _loads(library):
            return EspeakInstall(library=library, data_path=data)
    return None


def _candidate_libraries() -> list[str]:
    found: list[str] = []
    if env := os.environ.get("PHONEMIZER_ESPEAK_LIBRARY"):
        found.append(env)
    for prefix in _BREW_PREFIXES:
        for name in ("libespeak-ng.dylib", "libespeak-ng.1.dylib"):
            path = Path(prefix) / "opt/espeak-ng/lib" / name
            if path.exists():
                found.append(str(path))
    if system := ctypes.util.find_library("espeak-ng"):
        found.append(system)
    return found


def _data_path_for(library: str) -> str | None:
    if env := os.environ.get("ESPEAK_DATA_PATH"):
        return env
    lib_dir = Path(library).resolve().parent
    for candidate in (
        lib_dir.parent / "share/espeak-ng-data",
        Path("/usr/share/espeak-ng-data"),
        Path("/usr/lib/x86_64-linux-gnu/espeak-ng-data"),
        Path("/usr/lib/aarch64-linux-gnu/espeak-ng-data"),
    ):
        if (candidate / "phontab").exists():
            return str(candidate)
    return None


def _loads(library: str) -> bool:
    """Load in a subprocess: a broken espeak build calls exit() instead of failing softly."""
    probe = (
        "import ctypes,sys;"
        f"lib=ctypes.cdll.LoadLibrary({library!r});"
        "sys.exit(0 if lib.espeak_Initialize(2,0,None,0)>0 else 1)"
    )
    try:
        done = subprocess.run(
            [sys.executable, "-c", probe], capture_output=True, timeout=10, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return done.returncode == 0
