"""Windows support that can be checked on any OS: espeak-ng lookup, hints, console output."""

import io
import sys
import types
from pathlib import Path

import pytest

from callback_voice.cli.console import use_utf8
from callback_voice.providers.tts import find_espeak as fe


@pytest.fixture
def no_system_espeak(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PHONEMIZER_ESPEAK_LIBRARY", raising=False)
    monkeypatch.setattr(fe, "_BREW_PREFIXES", ())
    monkeypatch.setattr(fe, "_WINDOWS_INSTALL_DIRS", ())
    monkeypatch.setattr(fe.ctypes.util, "find_library", lambda _name: None)


def _fake_loader(monkeypatch: pytest.MonkeyPatch, library: Path) -> None:
    module = types.ModuleType("espeakng_loader")
    module.get_library_path = lambda: library  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "espeakng_loader", module)


def test_windows_falls_back_to_the_bundled_library(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, no_system_espeak: None
) -> None:
    library = tmp_path / "libespeak-ng.dll"
    _fake_loader(monkeypatch, library)
    monkeypatch.setattr(fe.sys, "platform", "win32")

    assert fe._candidate_libraries() == [str(library)]


def test_bundled_library_is_not_used_off_windows(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, no_system_espeak: None
) -> None:
    _fake_loader(monkeypatch, tmp_path / "libespeak-ng.dylib")
    monkeypatch.setattr(fe.sys, "platform", "darwin")

    assert fe._candidate_libraries() == []


def test_windows_installer_location_comes_before_the_bundled_library(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, no_system_espeak: None
) -> None:
    installed = tmp_path / "eSpeak NG"
    installed.mkdir()
    (installed / "libespeak-ng.dll").touch()
    _fake_loader(monkeypatch, tmp_path / "bundled.dll")
    monkeypatch.setattr(fe, "_WINDOWS_INSTALL_DIRS", (str(installed),))
    monkeypatch.setattr(fe.sys, "platform", "win32")

    assert fe._candidate_libraries() == [
        str(installed / "libespeak-ng.dll"),
        str(tmp_path / "bundled.dll"),
    ]


def test_data_folder_beside_the_library_is_found(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("ESPEAK_DATA_PATH", raising=False)
    data = tmp_path / "espeak-ng-data"
    data.mkdir()
    (data / "phontab").touch()

    assert fe._data_path_for(str(tmp_path / "libespeak-ng.dll")) == str(data)


@pytest.mark.parametrize(
    ("platform", "expected"),
    [("win32", "espeak-ng/releases"), ("darwin", "brew install"), ("linux", "apt install")],
)
def test_install_hint_fits_the_platform(
    monkeypatch: pytest.MonkeyPatch, platform: str, expected: str
) -> None:
    monkeypatch.setattr(fe.sys, "platform", platform)

    assert expected in fe.espeak_install_hint()


def test_redirected_windows_output_can_print_the_marks(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="cp1252")
    monkeypatch.setattr(sys, "platform", "win32")

    use_utf8((stream,))
    stream.write("✓ ✕ ●")
    stream.flush()

    assert raw.getvalue().decode("utf-8") == "✓ ✕ ●"


def test_output_is_left_alone_off_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "platform", "linux")

    use_utf8((stream,))

    assert stream.encoding == "cp1252"
