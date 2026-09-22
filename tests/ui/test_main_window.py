"""Tests for the main window and its export/state wiring.

Everything runs offscreen with an injected fake worker factory and mocked
export helpers: no inference, no subprocess and no network access ever happen
here. ``Settings`` uses an isolated organization/application pair so the real
user configuration is never touched.
"""

import os

import pytest
from PySide6.QtCore import QObject, Signal

from separateur_de_stems.ui import main_window as main_window_module
from separateur_de_stems.ui.main_window import MainWindow
from separateur_de_stems.ui.settings import Settings

ORG = "TestOrg"
APP = "TestApp"


@pytest.fixture
def settings():
    """A Settings instance isolated from the real user configuration."""
    store = Settings(organization=ORG, application=APP)
    store.clear()
    yield store
    store.clear()


class FakeWorker(QObject):
    """Minimal stand-in for ``SeparationWorker`` exposing the same signals."""

    progress = Signal(int, str)
    finished = Signal(dict)
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

    window.start_separation()

    assert len(fake_factory.created) == 1
    assert fake_factory.created[0].started is True
    assert window.separate_button.text() == window.tr("Cancel")
    assert window.drop_zone.isEnabled() is False
    assert window.output_edit.isEnabled() is False
    for checkbox in window.stem_checkboxes.values():
        assert checkbox.isEnabled() is False


def test_cancel_separation_requests_cancel(qtbot, settings, tmp_path, fake_factory):
    window = _make_window(qtbot, settings, worker_factory=fake_factory)
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"")
    window.open_file(str(audio))
    window.output_edit.setText(str(tmp_path / "out"))
    window.start_separation()

    window.cancel_separation()
    assert fake_factory.created[0].cancel_calls == 1


def test_on_progress_updates_bar_and_status(qtbot, settings):
    window = _make_window(qtbot, settings)
    window.on_progress(42, "Separating vocals")
    assert window.progress_bar.value() == 42
    assert "Separating vocals" in window.status_label.text()


def test_on_finished_exports_wav_and_mp3(qtbot, settings, tmp_path, monkeypatch):
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

    window = _make_window(qtbot, settings)
    audio = tmp_path / "My Song.wav"
    audio.write_bytes(b"")
    window.open_file(str(audio))
    output_dir = tmp_path / "out"
    window.output_edit.setText(str(output_dir))

    mock_dir = output_dir / "My Song"
    expected_wav = os.path.join(str(mock_dir), "My Song_vocals.wav")
    expected_mp3 = os.path.join(str(mock_dir), "My Song_vocals.mp3")
    raw_source = tmp_path / "raw_vocals.wav"
    raw_source.write_bytes(b"")
    window.on_finished({"vocals": str(raw_source)})

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
    window.start_separation()

    window.on_finished({"vocals": str(tmp_path / "raw.wav")})

    assert window.separate_button.text() == window.tr("Separate")
    assert window.drop_zone.isEnabled() is True
    assert window.output_edit.isEnabled() is True


def test_on_failed_logs_and_resets(qtbot, settings, tmp_path, fake_factory):
    window = _make_window(qtbot, settings, worker_factory=fake_factory)
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"")
    window.open_file(str(audio))
    window.output_edit.setText(str(tmp_path / "out"))
    window.start_separation()

    window.on_failed("engine exploded")
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
    assert window.separate_button.text() == window.tr("Separate")
    assert window.tr("Cancelled") in window.log_view.toPlainText()


def test_remove_intermediates_is_bounded_to_output_dir(
    qtbot, settings, tmp_path, monkeypatch
):
    """An intermediate is only removed when it lives under the output folder."""
    monkeypatch.setattr(main_window_module, "to_wav24", lambda src, dest: dest)
    monkeypatch.setattr(main_window_module, "to_mp3_320", lambda src, dest: dest)

    window = _make_window(qtbot, settings)
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"")
    window.open_file(str(audio))
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    window.output_edit.setText(str(output_dir))

    inside = output_dir / "raw_vocals.wav"
    inside.write_bytes(b"")
    outside = tmp_path / "raw_instrumental.wav"
    outside.write_bytes(b"")

    window.on_finished(
        {"vocals": str(inside), "instrumental": str(outside)}
    )

    assert inside.exists() is False
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

    partial = output_dir / "song_vocals.part.wav"
    partial.write_bytes(b"half written")

    window.on_cancelled()

    assert partial.exists() is False
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
