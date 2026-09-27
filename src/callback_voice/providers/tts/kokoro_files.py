from pathlib import Path

import httpx

from callback_voice.core.paths import model_cache_dir
from callback_voice.errors import ProviderError

_RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
MODEL_FILE = "kokoro-v1.0.int8.onnx"
VOICES_FILE = "voices-v1.0.bin"


def kokoro_dir() -> Path:
    return model_cache_dir() / "kokoro"


def kokoro_files_present() -> bool:
    return all((kokoro_dir() / name).is_file() for name in (MODEL_FILE, VOICES_FILE))


def ensure_kokoro_files() -> tuple[Path, Path]:
    """Download the Kokoro v1.0 int8 model (Apache-2.0) and voices once; return their paths."""
    directory = kokoro_dir()
    directory.mkdir(parents=True, exist_ok=True)
    for name in (MODEL_FILE, VOICES_FILE):
        target = directory / name
        if not target.is_file():
            _download(f"{_RELEASE}/{name}", target)
    return directory / MODEL_FILE, directory / VOICES_FILE


def _download(url: str, target: Path) -> None:
    partial = target.with_suffix(target.suffix + ".part")
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=60.0) as response:
            response.raise_for_status()
            with partial.open("wb") as out:
                for chunk in response.iter_bytes(1 << 20):
                    out.write(chunk)
    except httpx.HTTPError as exc:
        partial.unlink(missing_ok=True)
        raise ProviderError(f"could not download {url}: {exc}") from exc
    partial.rename(target)
