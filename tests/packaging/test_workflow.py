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
    """Direct dependencies are strict without claiming a transitive lock."""
    text = Path("requirements/macos-arm64.lock").read_text()
    assert "PySide6==6.11.2" in text
    assert "audio-separator==0.47.0" in text
    assert "pyinstaller==6.22.3" in text.lower()
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


def test_workflow_has_read_only_permissions_and_direct_inventory():
    data = _load()
    assert data["permissions"] == {"contents": "read"}
    install = next(
        step["run"] for step in data["jobs"]["build"]["steps"]
        if step.get("name") == "Install Python dependencies for development build"
    )
    assert "requirements/macos-arm64.lock" in install
    assert "--upgrade pip" not in install
    assert "--require-hashes" not in install


def test_tag_upload_depends_on_release_gate():
    steps = _load()["jobs"]["build"]["steps"]
    gate = next(step for step in steps if step.get("id") == "release_gate")
    upload = next(step for step in steps if step.get("name") == "Upload the macOS artifact")
    assert "refs/tags/" in gate["if"]
    assert "scripts.validate_release" in gate["run"]
    assert "steps.release_gate.outcome == 'success'" in upload["if"]


def test_tag_installs_only_validated_transitive_lock_with_hashes():
    steps = _load()["jobs"]["build"]["steps"]
    installs = [step for step in steps if step.get("name", "").startswith("Install Python dependencies")]
    tag_install = next(step for step in installs if "tagged release" in step["name"])
    dev_install = next(step for step in installs if "development build" in step["name"])
    assert "refs/tags/" in tag_install["if"]
    assert "!startsWith" in dev_install["if"]
    assert tag_install["run"] == (
        "python -m pip install --require-hashes "
        "-r requirements/macos-arm64-transitive.lock"
    )
    assert "macos-arm64.lock" not in tag_install["run"]
    assert "macos-arm64.lock" in dev_install["run"]


def test_workflow_validates_binary_architecture_smokes_and_hashes_artifact():
    text = _workflow_text()
    assert "--platform darwin" in text
    assert "otool -L" in text
    assert "-m scripts.smoke_bundle" in text
    assert "shasum -a 256" in text
    assert "du -h" in text


def test_workflow_validates_source_and_bundled_dependencies_before_archive():
    steps = _load()["jobs"]["build"]["steps"]
    archive_index = next(i for i, step in enumerate(steps) if step.get("name") == "Package the .app as a zip")
    validation_steps = [
        (i, step) for i, step in enumerate(steps)
        if "validate_release" in step.get("run", "") and "--ffmpeg" in step.get("run", "")
    ]
    assert len(validation_steps) >= 2
    assert all(i < archive_index for i, _ in validation_steps)
    assert any("StemSeparator.app" in step["run"] for _, step in validation_steps)
    assert all("otool" in step["run"] or "--platform darwin" in step["run"] for _, step in validation_steps)


def test_workflow_validates_complete_app_macho_closure_before_archive():
    steps = _load()["jobs"]["build"]["steps"]
    archive_index = next(i for i, step in enumerate(steps) if step.get("name") == "Package the .app as a zip")
    closure_index = next(
        i for i, step in enumerate(steps)
        if "--app dist/StemSeparator.app" in step.get("run", "")
    )
    closure_command = steps[closure_index]["run"]
    assert closure_index < archive_index
    assert "--closure-report" in closure_command
    assert "ffprobe" in closure_command


def test_workflow_verifies_archive_checksum_before_upload():
    steps = _load()["jobs"]["build"]["steps"]
    upload_index = next(i for i, step in enumerate(steps) if step.get("name") == "Upload the macOS artifact")
    checksum_index = next(i for i, step in enumerate(steps) if "shasum -a 256 -c" in step.get("run", ""))
    assert checksum_index < upload_index
