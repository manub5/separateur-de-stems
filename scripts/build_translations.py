"""Build the Qt translation catalogs for the stem separator UI.

Extracts translatable strings from the ``ui`` package with
``pyside6-lupdate`` and compiles the ``.ts`` catalogs to ``.qm`` with
``pyside6-lrelease``. In ``check`` mode both tools run against a temporary
copy of the ``.ts`` so the working tree is never written to; the build fails
when the committed ``.qm`` differs from the freshly compiled catalog.
"""

import argparse
import filecmp
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

__all__ = [
    "source_files",
    "ts_path",
    "qm_path",
    "build",
    "main",
]

_REPO_ROOT = Path(__file__).resolve().parent.parent
_UI_DIR = _REPO_ROOT / "separateur_de_stems" / "ui"
_I18N_DIR = _UI_DIR / "i18n"
_BASENAME = "stem_separator_{language}"
_DEFAULT_LANGUAGE = "fr"


def source_files() -> list[str]:
    """Return the sorted Python sources scanned for translatable strings."""
    return sorted(str(path) for path in _UI_DIR.glob("*.py"))


def ts_path(language: str = _DEFAULT_LANGUAGE) -> str:
    """Path of the translation source file for ``language``."""
    return str(_I18N_DIR / f"{_BASENAME.format(language=language)}.ts")


def qm_path(language: str = _DEFAULT_LANGUAGE) -> str:
    """Path of the compiled translation file for ``language``."""
    return str(_I18N_DIR / f"{_BASENAME.format(language=language)}.qm")


def _tool_path(name: str) -> str:
    """Locate a Qt Linguist tool, preferring PATH and falling back to the venv."""
    found = shutil.which(name)
    if found:
        return found
    candidate = Path(sys.executable).parent / name
    if candidate.is_file():
        return str(candidate)
    print(f"error: required tool not found: {name}", file=sys.stderr)
    return ""


def _run_tool(command: list[str]) -> int:
    """Run a Qt Linguist tool, forwarding its diagnostics, and return its code."""
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
    return result.returncode


def build(check: bool = False) -> int:
    """Update the ``.ts`` catalog and compile it.

    Returns 0 on success. With ``check=True`` the ``.ts`` is copied to a
    temporary directory, refreshed there and compiled to a temporary ``.qm``;
    it is then compared with the committed catalog. Nothing under the working
    tree is written and 1 is returned when the catalogs differ.
    """
    lupdate = _tool_path("pyside6-lupdate")
    lrelease = _tool_path("pyside6-lrelease")
    if not lupdate or not lrelease:
        return 1

    if check:
        return _check(lupdate, lrelease)

    ts_file = ts_path()
    qm_file = qm_path()

    if _run_tool([lupdate, *source_files(), "-ts", ts_file]) != 0:
        return 1
    if _run_tool([lrelease, ts_file, "-qm", qm_file]) != 0:
        return 1
    return 0


def _check(lupdate: str, lrelease: str) -> int:
    """Refresh and compile a temporary copy, then compare it to the committed catalog."""
    ts_file = Path(ts_path())
    qm_file = Path(qm_path())

    if not ts_file.is_file():
        print(f"error: {ts_file} does not exist", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_ts = Path(tmp_dir) / ts_file.name
        tmp_qm = Path(tmp_dir) / qm_file.name
        shutil.copyfile(ts_file, tmp_ts)

        if _run_tool([lupdate, *source_files(), "-ts", str(tmp_ts)]) != 0:
            return 1
        if _run_tool([lrelease, str(tmp_ts), "-qm", str(tmp_qm)]) != 0:
            return 1

        if not qm_file.is_file() or not filecmp.cmp(qm_file, tmp_qm, shallow=False):
            print(f"error: {qm_file} is out of date", file=sys.stderr)
            return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the committed catalog is up to date without writing it",
    )
    args = parser.parse_args(argv)
    return build(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
