import base64
import json
from importlib.resources import files
from pathlib import Path

from callback_voice.core.models.run_result import RunResult
from callback_voice.report.build_report import build_report

_SLOT = "/*__CALLBACK_REPORT_DATA__*/null"
_FONT_SLOT = "/*__CALLBACK_FONT__*/"


def write_report(result: RunResult, run_dir: Path, *, audio: bool = True) -> Path:
    """Write ``report.html``: one self-contained file that opens offline.

    The run's data (and each call's audio as MP3) is embedded as JSON in the page, with
    the display font as a data URI, so the file can be attached to a pull request or a CI
    artifact on its own.
    """
    template = files("callback_voice.report").joinpath("assets/report.html").read_text("utf-8")
    data = json.dumps(build_report(result, run_dir, audio=audio), separators=(",", ":"))
    # Inside <script>, "</" could close the tag early; "<\/" is the same JSON string.
    font = files("callback_voice.report").joinpath("assets/display.woff2").read_bytes()
    page = template.replace(_FONT_SLOT, base64.b64encode(font).decode("ascii"), 1)
    page = page.replace(_SLOT, data.replace("</", "<\\/"), 1)
    path = run_dir / "report.html"
    path.write_text(page, encoding="utf-8")
    return path
