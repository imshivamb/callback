import logging
import time
from pathlib import Path

_QUIET = ("httpx", "httpcore", "faster_whisper", "websockets", "huggingface_hub")
_FORMAT = "%(asctime)s.%(msecs)03d %(message)s"
_DATE = "%Y-%m-%d %H:%M:%S"


def configure_agent_logging(log_dir: Path, profile: str, port: int, *, verbose: bool) -> Path:
    """Send the agent's conversation log to a new file for this run, and to the console.

    The file always gets everything the agent decides (what it heard, said, why it
    yielded), with dated, millisecond timestamps. Each run gets its own file named
    ``<YYYYmmdd-HHMMSS>-<profile>-<port>.log``; an existing file is never
    overwritten. ``verbose`` only controls the console.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = log_dir / f"{stamp}-{profile}-{port}.log"
    suffix = 1
    while path.exists():
        path = log_dir / f"{stamp}-{profile}-{port}-{suffix}.log"
        suffix += 1

    formatter = logging.Formatter(_FORMAT, _DATE)
    file_handler = logging.FileHandler(path, mode="x", encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO if verbose else logging.WARNING)
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers[:] = [file_handler, console_handler]
    for noisy in _QUIET:
        logging.getLogger(noisy).setLevel(logging.WARNING)
    return path
