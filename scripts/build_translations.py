"""Build the Qt translation catalogs for the stem separator UI.

Extracts translatable strings from the ``ui`` package with
``pyside6-lupdate`` and compiles the ``.ts`` catalogs to ``.qm`` with
``pyside6-lrelease``. In ``check`` mode the compilation goes to a temporary
file so the committed ``.qm`` is never overwritten; the build fails when the
committed catalog differs from the freshly compiled one.
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
_BASENAME = "stem_separator_fr"
_DEFAULT_LANGUAGE = "fr"


def source_files() -> list[str]:
    """Return the sorted Python sources scanned for translatable strings."""
    return sorted(str(path) for path in _UI_DIR.glob("*.py"))


def ts_path(language: str = _DEFAULT_LANGUAGE) -> str:
    """Path of the translation source file for ``language``."""
    return str(_I18N_DIR / f"{_BASENAME}.ts")


def qm_path(language: str = _DEFAULT_LANGUAGE) -> str:
    """Path of the compiled translation file for ``language``."""
    return str(_I18N_DIR / f"{_BASENAME}.qm")


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


def build(check: bool = False) -> int:
    """Update the ``.ts`` catalog and compile it.

    Returns 0 on success. With ``check=True`` the ``.qm`` is compiled to a
    temporary file and compared with the committed one; nothing is written
    and 1 is returned when they differ.
    """
    lupdate = _tool_path("pyside6-lupdate")
    lrelease = _tool_path("pyside6-lrelease")
    if not lupdate or not lrelease:
        return 1

    ts_file = ts_path()
    qm_file = qm_path()

    update = subprocess.run(
        [lupdate, *source_files(), "-ts", ts_file],
        capture_output=True,
        text=True,
    )
    if update.returncode != 0:
        print(update.stderr, file=sys.stderr)
        return 1

    if check:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_qm = Path(tmp_dir) / Path(qm_file).name
            compile_result = subprocess.run(
                [lrelease, ts_file, "-qm", str(tmp_qm)],
                capture_output=True,
                text=True,
            )
            if compile_result.returncode != 0:
                print(compile_result.stderr, file=sys.stderr)
                return 1
            committed = Path(qm_file)
            if not committed.is_file() or not filecmp.cmp(
                committed, tmp_qm, shallow=False
            ):
                print(f"error: {qm_file} is out of date", file=sys.stderr)
                return 1
        return 0

    compile_result = subprocess.run(
        [lrelease, ts_file, "-qm", qm_file],
        capture_output=True,
        text=True,
    )
    if compile_result.returncode != 0:
        print(compile_result.stderr, file=sys.stderr)
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
