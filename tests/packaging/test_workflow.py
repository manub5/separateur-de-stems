"""Static checks for the macOS GitHub Actions build workflow.

The workflow cannot run locally (no macOS runner), so it is validated
statically: YAML validity and presence of the key build/test steps.
"""

from pathlib import Path

import yaml

WORKFLOW = Path(".github/workflows/build-macos.yml")


def _load() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())


def _workflow_text() -> str:
    return WORKFLOW.read_text()


def test_workflow_file_exists():
    assert WORKFLOW.is_file()


def test_workflow_is_valid_yaml_with_jobs():
    data = _load()
    assert isinstance(data, dict)
    assert "jobs" in data
    assert data["jobs"]


def test_workflow_triggers_on_tags_and_manual():
    data = _load()
    assert "workflow_dispatch" in data[True]
    assert "push" in data[True]
    assert "v*" in data[True]["push"]["tags"]


def test_workflow_uses_macos_arm64_runner():
    assert "macos-14" in _workflow_text()


def test_workflow_installs_python_and_dependencies():
    text = _workflow_text()
    # Actions are pinned to commit SHAs (semgrep); the version is in the
    # trailing comment, e.g. actions/setup-python@<sha> # v5.6.0
    assert "actions/setup-python@" in text
    assert "# v5" in text
    assert "3.12" in text
    assert "pyinstaller" in text.lower()


def test_workflow_pins_dependency_versions():
    """Dependencies are pinned to the locally validated stack."""
    text = _workflow_text()
    assert "PySide6==6.11.2" in text
    assert "audio-separator==0.47.0" in text
    assert "pyinstaller==6.22.3" in text
    assert "soundfile==" in text
    assert "pytest==" in text
    assert "pytest-qt==" in text


def test_workflow_installs_ffmpeg():
    assert "brew install ffmpeg" in _workflow_text()


def test_workflow_runs_tests_offscreen_without_slow():
    data = _load()
    steps = data["jobs"]["build"]["steps"]
    test_steps = [
        step for step in steps if "pytest" in step.get("run", "")
    ]
    assert test_steps
    assert any(
        step.get("env", {}).get("QT_QPA_PLATFORM") == "offscreen"
        for step in test_steps
    )
    assert 'not slow' in "".join(step.get("run", "") for step in test_steps)


def test_workflow_checks_translations():
    assert "build_translations" in _workflow_text()


def test_workflow_builds_with_pyinstaller_spec():
    assert "packaging/stem-separator.spec" in _workflow_text()


def test_workflow_smoke_tests_the_app_binary():
    text = _workflow_text()
    assert "StemSeparator.app/Contents/MacOS/StemSeparator" in text
    assert "--help" in text


def test_workflow_packages_and_uploads_artifact():
    text = _workflow_text()
    assert "ditto -c -k" in text
    assert "actions/upload-artifact@" in text
    assert "# v4" in text
    assert "StemSeparator-macos" in text
    assert "dist/StemSeparator-macos.zip" in text
