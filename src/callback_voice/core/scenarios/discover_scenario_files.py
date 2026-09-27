from pathlib import Path

from callback_voice.errors import ScenarioError

_SUFFIXES = (".yaml", ".yml")


def discover_scenario_files(path: Path) -> list[Path]:
    """Return scenario files under ``path`` (a file or a directory), sorted for stable runs.

    Hidden files and ``callback.yaml`` itself are skipped.
    """
    if path.is_file():
        return [path]
    if not path.is_dir():
        raise ScenarioError(f"no such file or directory: {path}")
    files = sorted(
        p
        for p in path.rglob("*")
        if p.suffix in _SUFFIXES
        and p.name != "callback.yaml"
        and not any(part.startswith(".") for part in p.relative_to(path).parts)
    )
    if not files:
        raise ScenarioError(f"no scenario files (*.yaml) found in {path}")
    return files
