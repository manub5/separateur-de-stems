"""Tests for the settings dialog and its main window integration.

Everything runs offscreen with an isolated ``Settings`` store and an injected
``cache_dir`` pointing at ``tmp_path``, so the real user configuration and the
project's own cache are never touched. No inference, subprocess or network
access ever happens here.
"""

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMessageBox

from separateur_de_stems.ui import main_window as main_window_module
from separateur_de_stems.ui.main_window import MainWindow
from separateur_de_stems.ui.settings import Settings
from separateur_de_stems.ui.settings_dialog import SettingsDialog

ORG = "TestOrg"
APP = "TestApp"


@pytest.fixture
def settings():
    """A Settings instance isolated from the real user configuration."""
    store = Settings(organization=ORG, application=APP)
    store.clear()
    yield store
    store.clear()


def _make_dialog(qtbot, settings, cache_dir):
    dialog = SettingsDialog(settings, cache_dir=str(cache_dir))
    qtbot.addWidget(dialog)
    return dialog


def test_initial_values_reflect_settings(qtbot, settings, tmp_path):
    settings.model_dir = "/some/models"
    settings.language = "fr"
    dialog = _make_dialog(qtbot, settings, tmp_path)
    assert dialog.model_dir_edit.text() == "/some/models"
    assert dialog.language_combo.currentData() == "fr"


def test_initial_values_fall_back_to_defaults(qtbot, settings, tmp_path):
    dialog = _make_dialog(qtbot, settings, tmp_path)
    assert dialog.model_dir_edit.text() == ""
    assert dialog.language_combo.currentData() == "system"


def test_accept_persists_model_dir_and_language(qtbot, settings, tmp_path):
    dialog = _make_dialog(qtbot, settings, tmp_path)
    dialog.model_dir_edit.setText("/tmp/models")
    dialog.language_combo.setCurrentIndex(
        dialog.language_combo.findData("fr")
    )

    dialog.accept()

    assert settings.model_dir == "/tmp/models"
    assert settings.language == "fr"


def test_reject_leaves_settings_untouched(qtbot, settings, tmp_path):
    settings.model_dir = "/original"
    settings.language = "en"
    dialog = _make_dialog(qtbot, settings, tmp_path)
    dialog.model_dir_edit.setText("/changed")
    dialog.language_combo.setCurrentIndex(
        dialog.language_combo.findData("fr")
    )

    dialog.reject()

    assert settings.model_dir == "/original"
    assert settings.language == "en"


def test_clear_cache_confirmed_deletes_contents_but_keeps_root(
    qtbot, settings, tmp_path, monkeypatch
):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "model.bin").write_bytes(b"data")
    sub = cache_dir / "nested"
    sub.mkdir()
    (sub / "file.txt").write_bytes(b"data")

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )

    dialog = _make_dialog(qtbot, settings, cache_dir)
    dialog._clear_cache()

    assert cache_dir.is_dir() is True
    assert list(cache_dir.iterdir()) == []


def test_clear_cache_declined_keeps_everything(
    qtbot, settings, tmp_path, monkeypatch
):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    keep = cache_dir / "model.bin"
    keep.write_bytes(b"data")

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.No,
    )

    dialog = _make_dialog(qtbot, settings, cache_dir)
    dialog._clear_cache()

    assert keep.exists() is True


def test_open_settings_opens_dialog(qtbot, settings, monkeypatch):
    calls = []

    class FakeDialog(QObject):
        languageChanged = Signal(str)

        def __init__(self, settings_arg, parent=None):
            super().__init__()
            calls.append((settings_arg, parent))
            self.accepted = True

        def exec(self):
            calls.append("exec")
            return 0

    monkeypatch.setattr(main_window_module, "SettingsDialog", FakeDialog)

    window = MainWindow(settings=settings)
    qtbot.addWidget(window)
    window.open_settings()

    assert calls[0][0] is settings
    assert "exec" in calls
