"""Tests for the main window and its export/state wiring.

Everything runs offscreen with an injected fake worker factory and mocked
export helpers: no inference, no subprocess and no network access ever happen
here. ``Settings`` uses an isolated organization/application pair so the real
user configuration is never touched.
"""

import os
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from PySide6.QtCore import QObject, Signal

from separateur_de_stems.ui import main_window as main_window_module
from separateur_de_stems.ui.main_window import MainWindow
from separateur_de_stems.ui.run_context import RunContext
from separateur_de_stems.ui.settings import Settings

ORG = "TestOrg"
APP = "TestApp"


@pytest.fixture
def settings():
    """A Settings instance isolated from the real user configuration."""
    store = Settings(organization=ORG, application=APP)
    store.clear()
    store.model_dir = os.getcwd()
    yield store
    store.clear()


class FakeWorker(QObject):
    """Minimal stand-in for ``SeparationWorker`` exposing the same signals."""

    progress = Signal(int, str)
    completed = Signal(dict)
    finished = Signal()
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.args = args
        self.kwargs = kwargs
        self.started = False
        self.cancel_calls = 0

    def start(self):
        self.started = True

    def request_cancel(self):
        self.cancel_calls += 1

    def deleteLater(self):
        self.deleted = True


def _make_window(qtbot, settings, worker_factory=None):
    window = MainWindow(settings=settings, worker_factory=worker_factory)
    qtbot.addWidget(window)
    return window


@pytest.fixture
def fake_factory():
    """Worker factory creating fakes and keeping them alive for inspection."""
    created = []

    def factory(input_path, stems, output_dir, model_dir):
        worker = FakeWorker(input_path, stems, output_dir, model_dir)
        created.append(worker)
        return worker

    factory.created = created
    return factory


def test_main_window_constructs(qtbot, settings):
    window = _make_window(qtbot, settings)
    assert window.windowTitle()
    assert window.separate_button.isEnabled() is False
    assert set(window.stem_checkboxes) == {
        "vocals",
        "instrumental",
        "drums",
        "bass",
        "guitar",
        "piano",
    }


def test_run_context_is_immutable():
    context = RunContext("in", "out", "models", frozenset({"vocals"}), "work")
    with pytest.raises(FrozenInstanceError):
        context.output_dir = "elsewhere"


def test_default_stems_come_from_settings(qtbot, settings):
    settings.default_stems = ["vocals", "drums"]
    window = _make_window(qtbot, settings)
    assert window.selected_stems() == {"vocals", "drums"}


def test_open_file_enables_button(qtbot, settings, tmp_path):
    window = _make_window(qtbot, settings)
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"")
    window.open_file(str(audio))
    assert window.current_file() == str(audio)
    assert window.separate_button.isEnabled() is True


def test_open_file_rejects_unsupported_extension(qtbot, settings, tmp_path):
    window = _make_window(qtbot, settings)
    other = tmp_path / "notes.txt"
    other.write_bytes(b"")
    window.open_file(str(other))
    assert window.current_file() is None
    assert window.separate_button.isEnabled() is False


def test_open_file_rejects_double_extension(qtbot, settings, tmp_path):
    window = _make_window(qtbot, settings)
    disguised = tmp_path / "song.wav.exe"
    disguised.write_bytes(b"")
    window.open_file(str(disguised))
    assert window.current_file() is None
    assert window.separate_button.isEnabled() is False


def test_open_file_rejects_extension_only_basename(qtbot, settings, tmp_path):
    """A hidden file named exactly ``.wav`` has no real extension."""
    window = _make_window(qtbot, settings)
    hidden = tmp_path / ".wav"
    hidden.write_bytes(b"")
    window.open_file(str(hidden))
    assert window.current_file() is None


def test_open_file_rejects_backup_extension(qtbot, settings, tmp_path):
    window = _make_window(qtbot, settings)
    backup = tmp_path / "song.wav.bak"
    backup.write_bytes(b"")
    window.open_file(str(backup))
    assert window.current_file() is None


def test_open_file_accepts_uppercase_extension(qtbot, settings, tmp_path):
    window = _make_window(qtbot, settings)
    audio = tmp_path / "SONG.WAV"
    audio.write_bytes(b"")
    window.open_file(str(audio))
    assert window.current_file() == str(audio)


def test_selected_stems_reflects_checkboxes(qtbot, settings):
    window = _make_window(qtbot, settings)
    window.stem_checkboxes["drums"].setChecked(True)
    window.stem_checkboxes["vocals"].setChecked(False)
    assert "drums" in window.selected_stems()
    assert "vocals" not in window.selected_stems()


def test_no_stem_selected_disables_button_even_with_file(qtbot, settings, tmp_path):
    window = _make_window(qtbot, settings)
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"")
    window.open_file(str(audio))
    for checkbox in window.stem_checkboxes.values():
        checkbox.setChecked(False)
    assert window.separate_button.isEnabled() is False


def test_start_separation_sets_running_state(qtbot, settings, tmp_path, fake_factory):
    window = _make_window(qtbot, settings, worker_factory=fake_factory)
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"")
    window.open_file(str(audio))
    window.output_edit.setText(str(tmp_path / "out"))
    settings.model_dir = str(tmp_path)

    window.start_separation()

    assert len(fake_factory.created) == 1
    assert fake_factory.created[0].started is True
    assert window.separate_button.text() == window.tr("Cancel")
    assert window.drop_zone.isEnabled() is False
    assert window.output_edit.isEnabled() is False
    assert window.open_button.isEnabled() is False
    assert window.choose_button.isEnabled() is False
    assert window._open_action.isEnabled() is False
    assert window._settings_action.isEnabled() is False
    for checkbox in window.stem_checkboxes.values():
        assert checkbox.isEnabled() is False


def test_cancel_separation_requests_cancel(qtbot, settings, tmp_path, fake_factory):
    window = _make_window(qtbot, settings, worker_factory=fake_factory)
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"")
    window.open_file(str(audio))
    window.output_edit.setText(str(tmp_path / "out"))
    settings.model_dir = str(tmp_path)
    window.start_separation()

    window.cancel_separation()
    assert fake_factory.created[0].cancel_calls == 1


def test_terminal_result_uses_captured_paths_and_stays_locked_until_thread_finished(
    qtbot, settings, tmp_path, fake_factory, monkeypatch
):
    exports = []
    monkeypatch.setattr(
        main_window_module,
        "to_wav24",
        lambda src, dest: exports.append(dest) or dest,
    )
    monkeypatch.setattr(
        main_window_module,
        "to_mp3_320",
        lambda src, dest: exports.append(dest) or dest,
    )
    audio = tmp_path / "original.wav"
    audio.write_bytes(b"audio")
    output = tmp_path / "original-output"
    settings.model_dir = str(tmp_path)
    window = _make_window(qtbot, settings, worker_factory=fake_factory)
    window.open_file(str(audio))
    window.output_edit.setText(str(output))
    window.start_separation()
    context = window._run_context
    raw = Path(context.workspace) / "vocals.wav"
    raw.write_bytes(b"raw")

    window._input_path = str(tmp_path / "changed.wav")
    window.output_edit.setText(str(tmp_path / "changed-output"))
    fake_factory.created[0].completed.emit(
        {"vocals": str(raw), "instrumental": str(raw)}
    )

    assert exports
    assert all(str(output) in path for path in exports)
    assert all("original_" in path for path in exports)
    assert window.drop_zone.isEnabled() is False
    assert window._worker is fake_factory.created[0]

    fake_factory.created[0].finished.emit()
    assert window.drop_zone.isEnabled() is True
    assert window._worker is None


def test_configured_model_directory_and_private_workspace_are_passed_to_worker(
    qtbot, settings, tmp_path, fake_factory
):
    model_dir = tmp_path / "custom-models"
    model_dir.mkdir()
    settings.model_dir = f"  {model_dir}  "
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"audio")
    window = _make_window(qtbot, settings, worker_factory=fake_factory)
    window.open_file(str(audio))
    window.output_edit.setText(str(tmp_path / "out"))

    window.start_separation()

    worker = fake_factory.created[0]
    assert worker.args[2] == window._run_context.workspace
    assert worker.args[3] == str(model_dir)


def test_missing_input_and_empty_output_do_not_start(
    qtbot, settings, tmp_path, fake_factory
):
    settings.model_dir = str(tmp_path)
    missing = tmp_path / "missing.wav"
    window = _make_window(qtbot, settings, worker_factory=fake_factory)
    window.open_file(str(missing))
    window.output_edit.setText("   ")

    window.start_separation()

    assert fake_factory.created == []


def test_incomplete_outputs_fail_and_cleanup_only_workspace(
    qtbot, settings, tmp_path, fake_factory
):
    settings.model_dir = str(tmp_path)
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"audio")
    output = tmp_path / "out"
    output.mkdir()
    user_file = output / "keep.wav"
    user_file.write_bytes(b"keep")
    window = _make_window(qtbot, settings, worker_factory=fake_factory)
    window.open_file(str(audio))
    window.output_edit.setText(str(output))
    window.start_separation()
    workspace = Path(window._run_context.workspace)
    partial = workspace / "partial.wav"
    partial.write_bytes(b"partial")

    fake_factory.created[0].completed.emit({})
    fake_factory.created[0].finished.emit()

    assert window.status_label.text() == window.tr("Failed")
    assert workspace.exists() is False
    assert user_file.read_bytes() == b"keep"


def test_active_close_is_deferred_until_native_thread_finish(
    qtbot, settings, tmp_path, fake_factory
):
    settings.model_dir = str(tmp_path)
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"audio")
    window = _make_window(qtbot, settings, worker_factory=fake_factory)
    window.open_file(str(audio))
    window.output_edit.setText(str(tmp_path / "out"))
    window.show()
    window.start_separation()

    window.close()

    assert window.isVisible() is True
    assert fake_factory.created[0].cancel_calls == 1
    fake_factory.created[0].cancelled.emit()
    fake_factory.created[0].finished.emit()
    qtbot.waitUntil(lambda: not window.isVisible())


def test_immediate_relaunch_is_blocked_until_native_thread_finish(
    qtbot, settings, tmp_path, fake_factory
):
    settings.model_dir = str(tmp_path)
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"audio")
    window = _make_window(qtbot, settings, worker_factory=fake_factory)
    window.open_file(str(audio))
    window.output_edit.setText(str(tmp_path / "out"))
    window.start_separation()
    fake_factory.created[0].cancelled.emit()

    window.start_separation()
    assert len(fake_factory.created) == 1

    fake_factory.created[0].finished.emit()
    window.start_separation()
    assert len(fake_factory.created) == 2


def test_native_finish_without_terminal_result_fails(
    qtbot, settings, tmp_path, fake_factory
):
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"audio")
    window = _make_window(qtbot, settings, worker_factory=fake_factory)
    window.open_file(str(audio))
    window.output_edit.setText(str(tmp_path / "out"))
    window.start_separation()

    fake_factory.created[0].finished.emit()

    assert window.status_label.text() == window.tr("Failed")
    assert "terminal" in window.log_view.toPlainText().lower()


def test_on_progress_updates_bar_and_status(qtbot, settings):
    window = _make_window(qtbot, settings)
    window.on_progress(42, "Separating vocals")
    assert window.progress_bar.value() == 42
    assert "Separating vocals" in window.status_label.text()


def test_on_finished_exports_wav_and_mp3(
    qtbot, settings, tmp_path, monkeypatch, fake_factory
):
    wav_calls = []
    mp3_calls = []

    def fake_wav24(src, dest):
        wav_calls.append((src, dest))
        return dest

    def fake_mp3_320(src, dest):
        mp3_calls.append((src, dest))
        return dest

    monkeypatch.setattr(main_window_module, "to_wav24", fake_wav24)
    monkeypatch.setattr(main_window_module, "to_mp3_320", fake_mp3_320)

    window = _make_window(qtbot, settings, worker_factory=fake_factory)
    audio = tmp_path / "My Song.wav"
    audio.write_bytes(b"")
    window.open_file(str(audio))
    output_dir = tmp_path / "out"
    window.output_edit.setText(str(output_dir))
    window.stem_checkboxes["instrumental"].setChecked(False)
    window.start_separation()

    mock_dir = output_dir / "My Song"
    expected_wav = os.path.join(str(mock_dir), "My Song_vocals.wav")
    expected_mp3 = os.path.join(str(mock_dir), "My Song_vocals.mp3")
    raw_source = Path(window._run_context.workspace) / "raw_vocals.wav"
    raw_source.write_bytes(b"")
    fake_factory.created[0].completed.emit({"vocals": str(raw_source)})
    fake_factory.created[0].finished.emit()

    assert (str(raw_source), expected_wav) in wav_calls
    assert (expected_wav, expected_mp3) in mp3_calls
    assert window.separate_button.text() == window.tr("Separate")


def test_on_finished_resets_running_state(
    qtbot, settings, tmp_path, monkeypatch, fake_factory
):
    monkeypatch.setattr(main_window_module, "to_wav24", lambda src, dest: dest)
    monkeypatch.setattr(main_window_module, "to_mp3_320", lambda src, dest: dest)

    window = _make_window(qtbot, settings, worker_factory=fake_factory)
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"")
    window.open_file(str(audio))
    window.output_edit.setText(str(tmp_path / "out"))
    window.stem_checkboxes["instrumental"].setChecked(False)
    window.start_separation()

    raw = Path(window._run_context.workspace) / "raw.wav"
    raw.write_bytes(b"raw")
    fake_factory.created[0].completed.emit({"vocals": str(raw)})

    assert window.separate_button.text() == window.tr("Cancel")
    assert window.drop_zone.isEnabled() is False
    fake_factory.created[0].finished.emit()
    assert window.separate_button.text() == window.tr("Separate")
    assert window.output_edit.isEnabled() is True


def test_button_is_not_cancellable_during_export(
    qtbot, settings, tmp_path, fake_factory, monkeypatch
):
    """During export there is no live worker, so cancel must be unavailable."""
    observed = []

    def probe_wav24(src, dest):
        observed.append(
            (
                window.separate_button.isEnabled(),
                window.separate_button.text(),
            )
        )
        return dest

    monkeypatch.setattr(main_window_module, "to_wav24", probe_wav24)
    monkeypatch.setattr(main_window_module, "to_mp3_320", lambda src, dest: dest)

    window = _make_window(qtbot, settings, worker_factory=fake_factory)
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"")
    window.open_file(str(audio))
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    window.output_edit.setText(str(output_dir))
    window.stem_checkboxes["instrumental"].setChecked(False)
    window.start_separation()

    raw = Path(window._run_context.workspace) / "raw_vocals.wav"
    raw.write_bytes(b"")
    fake_factory.created[0].completed.emit({"vocals": str(raw)})

    assert observed, "export was never reached"
    for enabled, text in observed:
        assert enabled is False
        assert text != window.tr("Cancel")
    fake_factory.created[0].finished.emit()
    assert window.separate_button.text() == window.tr("Separate")


def test_cancel_without_worker_is_harmless(qtbot, settings):
    window = _make_window(qtbot, settings)
    window.cancel_separation()
    window.cancel_separation()
    assert window.separate_button.text() == window.tr("Separate")


def test_on_failed_logs_and_resets(qtbot, settings, tmp_path, fake_factory):
    window = _make_window(qtbot, settings, worker_factory=fake_factory)
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"")
    window.open_file(str(audio))
    window.output_edit.setText(str(tmp_path / "out"))
    window.start_separation()

    window.on_failed("engine exploded")
    assert window.separate_button.text() == window.tr("Cancel")
    fake_factory.created[0].finished.emit()
    assert window.separate_button.text() == window.tr("Separate")
    assert "engine exploded" in window.log_view.toPlainText()


def test_on_cancelled_resets(qtbot, settings, tmp_path, fake_factory):
    window = _make_window(qtbot, settings, worker_factory=fake_factory)
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"")
    window.open_file(str(audio))
    window.output_edit.setText(str(tmp_path / "out"))
    window.start_separation()

    window.on_cancelled()
    assert window.separate_button.text() == window.tr("Cancel")
    fake_factory.created[0].finished.emit()
    assert window.separate_button.text() == window.tr("Separate")
    assert window.tr("Cancelled") in window.log_view.toPlainText()


def test_success_never_deletes_sources_outside_workspace(
    qtbot, settings, tmp_path, monkeypatch, fake_factory
):
    """Cleanup is confined to the private workspace, not inferred sources."""
    monkeypatch.setattr(main_window_module, "to_wav24", lambda src, dest: dest)
    monkeypatch.setattr(main_window_module, "to_mp3_320", lambda src, dest: dest)

    window = _make_window(qtbot, settings, worker_factory=fake_factory)
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"")
    window.open_file(str(audio))
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    window.output_edit.setText(str(output_dir))
    window.start_separation()

    inside = output_dir / "raw_vocals.wav"
    inside.write_bytes(b"")
    outside = tmp_path / "raw_instrumental.wav"
    outside.write_bytes(b"")

    fake_factory.created[0].completed.emit(
        {"vocals": str(inside), "instrumental": str(outside)}
    )
    fake_factory.created[0].finished.emit()

    assert inside.exists() is True
    assert outside.exists() is True


def test_on_cancelled_removes_only_run_partials(
    qtbot, settings, tmp_path, fake_factory
):
    """Cancelling deletes files created during the run, never pre-existing ones."""
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    preexisting = output_dir / "previous_song.wav"
    preexisting.write_bytes(b"keep me")

    window = _make_window(qtbot, settings, worker_factory=fake_factory)
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"")
    window.open_file(str(audio))
    window.output_edit.setText(str(output_dir))
    window.start_separation()

    workspace = Path(window._run_context.workspace)
    workspace_partial = workspace / "song_vocals.part.wav"
    workspace_partial.write_bytes(b"half written")
    partial = output_dir / "unrelated.part.wav"
    partial.write_bytes(b"half written")

    window.on_cancelled()
    fake_factory.created[0].finished.emit()

    assert workspace.exists() is False
    assert partial.exists() is True
    assert preexisting.read_bytes() == b"keep me"

    window.on_cancelled()
    assert preexisting.read_bytes() == b"keep me"


def test_on_finished_exports_only_requested_stems(
    qtbot, settings, tmp_path, fake_factory, monkeypatch
):
    """Only the stems requested at launch are exported, not every output key."""
    wav_calls = []

    def fake_wav24(src, dest):
        wav_calls.append((src, dest))
        return dest

    monkeypatch.setattr(main_window_module, "to_wav24", fake_wav24)
    monkeypatch.setattr(main_window_module, "to_mp3_320", lambda src, dest: dest)

    window = _make_window(qtbot, settings, worker_factory=fake_factory)
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"")
    window.open_file(str(audio))
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    window.output_edit.setText(str(output_dir))

    window.stem_checkboxes["instrumental"].setChecked(False)
    window.start_separation()

    vocals_src = output_dir / "raw_vocals.wav"
    vocals_src.write_bytes(b"")
    instrumental_src = output_dir / "raw_instrumental.wav"
    instrumental_src.write_bytes(b"")

    window.on_finished(
        {"vocals": str(vocals_src), "instrumental": str(instrumental_src)}
    )

    exported_sources = {os.path.basename(src) for src, _ in wav_calls}
    assert "raw_vocals.wav" in exported_sources
    assert "raw_instrumental.wav" not in exported_sources
    assert instrumental_src.exists() is True
