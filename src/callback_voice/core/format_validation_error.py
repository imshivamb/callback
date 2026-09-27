from pathlib import Path

from pydantic import ValidationError


def format_validation_error(error: ValidationError, source: Path) -> str:
    """Render a Pydantic error as ``file: field.path: message`` lines a human can act on."""
    lines = [f"{source} is invalid:"]
    for issue in error.errors():
        location = ".".join(str(part) for part in issue["loc"] if part != "__root__")
        message = issue["msg"].removeprefix("Value error, ")
        lines.append(f"  {location or '(top level)'}: {message}")
    return "\n".join(lines)
