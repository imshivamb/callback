import ctypes
import ctypes.util
import os
import subprocess
import sys
from dataclasses import dataclass
from functools import cache
from pathlib import Path

_BREW_PREFIXES = ("/opt/homebrew", "/usr/local")
# Where the eSpeak NG Windows installer puts the library, with espeak-ng-data beside it.
_WINDOWS_INSTALL_DIRS = ("C:/Program Files/eSpeak NG", "C:/Program Files (x86)/eSpeak NG")


@dataclass(frozen=True, slots=True)
class EspeakInstall:
    library: str
    data_path: str


@cache
def find_espeak() -> EspeakInstall | None:
    """Locate a working espeak-ng shared library and its data directory.

    A system install is preferred: the library bundled by ``espeakng-loader`` on
    macOS arm64 ignores the data path it is given. On Windows, where espeak-ng has no
    package manager install, that bundled library is the last resort; it arrives with
    the ``local`` extra through kokoro-onnx. ``PHONEMIZER_ESPEAK_LIBRARY`` and
    ``ESPEAK_DATA_PATH`` override detection.
    """
    for library in _candidate_libraries():
        data = _data_path_for(library)
        if data is not None and _loads(library, data):
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
    if sys.platform == "win32":
        for folder in _WINDOWS_INSTALL_DIRS:
            path = Path(folder) / "libespeak-ng.dll"
            if path.exists():
                found.append(str(path))
    if system := ctypes.util.find_library("espeak-ng"):
        found.append(system)
    if sys.platform == "win32" and (bundled := _espeakng_loader_library()):
        found.append(bundled)
    return found


def _espeakng_loader_library() -> str | None:
    try:
        import espeakng_loader
    except ImportError:
        return None
    return str(espeakng_loader.get_library_path())


def _data_path_for(library: str) -> str | None:
    if env := os.environ.get("ESPEAK_DATA_PATH"):
        return env
    lib_dir = Path(library).resolve().parent
    for candidate in (
        lib_dir.parent / "share/espeak-ng-data",
        lib_dir / "espeak-ng-data",  # Windows installer and espeakng-loader
        Path("/usr/share/espeak-ng-data"),
        Path("/usr/lib/x86_64-linux-gnu/espeak-ng-data"),
        Path("/usr/lib/aarch64-linux-gnu/espeak-ng-data"),
    ):
        if (candidate / "phontab").exists():
            return str(candidate)
    return None


def _loads(library: str, data_path: str) -> bool:
    """Load in a subprocess: a broken espeak build calls exit() instead of failing softly.

    The data path is passed on Windows only: there no library has a built-in default
    that points at real data, while elsewhere the probe stays as it has been tested.
    """
    path_arg = repr(data_path.encode()) if sys.platform == "win32" else "None"
    probe = (
        "import ctypes,sys;"
        f"lib=ctypes.cdll.LoadLibrary({library!r});"
        f"sys.exit(0 if lib.espeak_Initialize(2,0,{path_arg},0)>0 else 1)"
    )
    try:
        done = subprocess.run(
            [sys.executable, "-c", probe], capture_output=True, timeout=10, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return done.returncode == 0


def espeak_install_hint() -> str:
    """How to get espeak-ng on this platform, for error messages and `doctor`."""
    if sys.platform == "win32":
        return (
            'pip install "callback-voice[local]" (bundles espeak-ng on Windows), or install '
            "eSpeak NG from https://github.com/espeak-ng/espeak-ng/releases"
        )
    return "macOS: brew install espeak-ng  ·  Debian/Ubuntu: sudo apt install espeak-ng"
