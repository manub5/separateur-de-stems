"""Tests for the Linux build script and the bundled binary."""

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path("packaging/build_linux.sh")
BINARY = Path("dist/StemSeparator/StemSeparator")


def test_build_script_exists_and_is_executable():
    assert SCRIPT.is_file()
    assert os.access(SCRIPT, os.X_OK)


def test_build_script_runs_bundle_smoke_as_module():
    assert "-m scripts.smoke_bundle" in SCRIPT.read_text()


def test_build_script_keeps_pyinstaller_cache_inside_project():
    script = SCRIPT.read_text()

    assert 'PYINSTALLER_CONFIG_DIR="$ROOT_DIR/.cache/pyinstaller"' in script
    assert "export PYINSTALLER_CONFIG_DIR" in script


@pytest.mark.slow
def test_bundled_binary_help_runs():
    if not BINARY.is_file():
        pytest.skip(f"bundled binary not built: {BINARY}")

    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    result = subprocess.run(
        [str(BINARY), "--help"],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "usage" in (result.stdout + result.stderr).lower()
