import os
import re
from pathlib import Path

_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")


def load_dotenv(start: Path) -> Path | None:
    """Load the nearest ``.env`` at or above ``start`` into the environment.

    Variables already set in the environment win, so CI secrets and shell exports
    are never overridden. Values are never logged. Returns the file loaded, if any.
    """
    for directory in (start.resolve(), *start.resolve().parents):
        candidate = directory / ".env"
        if candidate.is_file():
            for raw in candidate.read_text(encoding="utf-8").splitlines():
                match = _LINE.match(raw)
                if match is None or raw.lstrip().startswith("#"):
                    continue
                key, value = match.groups()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                    value = value[1:-1]
                os.environ.setdefault(key, value)
            return candidate
    return None
