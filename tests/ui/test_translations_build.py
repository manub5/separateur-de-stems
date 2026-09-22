"""Tests for the translation build script.

The build spawns the Qt Linguist tools (``pyside6-lupdate`` and
``pyside6-lrelease``). Tests must never overwrite the committed ``.ts`` /
``.qm`` files in ``separateur_de_stems/ui/i18n``: every compilation goes to a
temporary directory, either by copying the sources or by passing an explicit
``-qm`` target. Qt is not required to start for the path-only tests.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from scripts import build_translations


def _tool(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    return str(Path(__import__("sys").executable).parent / name)


def test_source_files_include_main_window():
    sources = build_translations.source_files()
    names = {Path(source).name for source in sources}
    assert "main_window.py" in names


def test_source_files_are_sorted():
    sources = build_translations.source_files()
    assert sources == sorted(sources)


def test_ts_path_points_under_i18n():
    path = Path(build_translations.ts_path("fr"))
    assert path.name == "stem_separator_fr.ts"
    assert path.parent.name == "i18n"


def test_qm_path_points_under_i18n():
    path = Path(build_translations.qm_path("fr"))
    assert path.name == "stem_separator_fr.qm"
    assert path.parent.name == "i18n"


def test_lrelease_compiles_copy_in_temporary_dir(tmp_path):
    tool = Path(_tool("pyside6-lrelease"))
    if not tool.exists():
        pytest.skip("pyside6-lrelease is not available")

    source_ts = Path(build_translations.ts_path("fr"))
    copied_ts = tmp_path / source_ts.name
    shutil.copy(source_ts, copied_ts)
    compiled_qm = tmp_path / "stem_separator_fr.qm"

    result = subprocess.run(
        [str(tool), str(copied_ts), "-qm", str(compiled_qm)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert compiled_qm.is_file()
    assert compiled_qm.stat().st_size > 0
    assert source_ts.is_file()
    assert Path(build_translations.qm_path("fr")).is_file()


def test_build_returns_zero_and_writes_catalog():
    assert build_translations.build() == 0
    assert Path(build_translations.qm_path("fr")).stat().st_size > 0
    assert Path(build_translations.ts_path("fr")).is_file()


def test_build_check_passes_after_build():
    assert build_translations.build() == 0
    assert build_translations.build(check=True) == 0


def test_build_check_fails_when_catalog_out_of_date(tmp_path, monkeypatch):
    tool = Path(_tool("pyside6-lrelease"))
    if not tool.exists():
        pytest.skip("pyside6-lrelease is not available")

    source_ts = tmp_path / "stem_separator_fr.ts"
    shutil.copy(Path(build_translations.ts_path("fr")), source_ts)
    stale_qm = tmp_path / "stem_separator_fr.qm"
    stale_qm.write_bytes(b"not a real catalog")

    monkeypatch.setattr(build_translations, "ts_path", lambda language="fr": str(source_ts))
    monkeypatch.setattr(build_translations, "qm_path", lambda language="fr": str(stale_qm))

    assert build_translations.build(check=True) == 1
    assert stale_qm.read_bytes() == b"not a real catalog"
