"""Tests for live language switching through ``retranslate_ui``.

Every test runs offscreen with an isolated ``Settings`` store and restores
English on teardown, so the global translator state never leaks. The strings
asserted here are real UI strings, not mocks: installing the French catalog
must actually change what the widgets display.
"""

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication

from separateur_de_stems.ui import i18n
from separateur_de_stems.ui.drop_zone import DropZone
from separateur_de_stems.ui.main_window import MainWindow
from separateur_de_stems.ui.settings import Settings
from separateur_de_stems.ui.settings_dialog import SettingsDialog

ORG = "TestOrg"
APP = "TestApp"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def restore_english(app):
    i18n.install_translators(app, "en")
    yield
    i18n.install_translators(app, "en")


@pytest.fixture
def settings():
    store = Settings(organization=ORG, application=APP)
    store.clear()
    yield store
    store.clear()


def _make_window(qtbot, settings):
    window = MainWindow(settings=settings)
    qtbot.addWidget(window)
    return window


def test_retranslate_ui_switches_separate_button_fr_then_en(
    qtbot, settings, app
):
    window = _make_window(qtbot, settings)
    assert window.separate_button.text() == "Separate"

    assert i18n.install_translators(app, "fr") == "fr"
    window.retranslate_ui()
    assert window.separate_button.text() == "Séparer"

    assert i18n.install_translators(app, "en") == "en"
    window.retranslate_ui()
    assert window.separate_button.text() == "Separate"


def test_retranslate_ui_keeps_cancel_label_while_running(
    qtbot, settings, app
):
    window = _make_window(qtbot, settings)
    window._set_running_state(True)
    assert window.separate_button.text() == "Cancel"

    assert i18n.install_translators(app, "fr") == "fr"
    window.retranslate_ui()
    assert window.separate_button.text() == "Annuler"

    assert i18n.install_translators(app, "en") == "en"
    window.retranslate_ui()
    assert window.separate_button.text() == "Cancel"


def test_retranslate_ui_uses_separate_label_while_exporting(
    qtbot, settings, app
):
    window = _make_window(qtbot, settings)
    window._set_running_state(True)
    window._set_exporting_state(True)
    assert window.separate_button.text() == "Separate"

    assert i18n.install_translators(app, "fr") == "fr"
    window.retranslate_ui()
    assert window.separate_button.text() == "Séparer"

    assert i18n.install_translators(app, "en") == "en"
    window.retranslate_ui()
    assert window.separate_button.text() == "Separate"


def test_change_event_language_change_updates_window_title(
    qtbot, settings, app
):
    window = _make_window(qtbot, settings)
    assert window.windowTitle() == "Stem Separator"

    i18n.install_translators(app, "fr")
    event = QEvent(QEvent.Type.LanguageChange)
    window.changeEvent(event)

    assert window.windowTitle() == "Séparateur de pistes"


def test_retranslate_ui_is_safe_when_widgets_not_built(qtbot, settings, app):
    window = _make_window(qtbot, settings)
    for attribute in (
        "_file_menu",
        "_open_action",
        "_quit_action",
        "_edit_menu",
        "_settings_action",
        "_help_menu",
        "_about_action",
        "drop_zone",
        "open_button",
        "stems_label",
        "stem_checkboxes",
        "output_label",
        "choose_button",
        "separate_button",
    ):
        delattr(window, attribute)

    i18n.install_translators(app, "fr")
    window.retranslate_ui()
    window.changeEvent(QEvent(QEvent.Type.LanguageChange))

    assert window.windowTitle() == "Séparateur de pistes"


def test_settings_dialog_emits_language_changed_when_language_changes(
    qtbot, settings, tmp_path
):
    dialog = SettingsDialog(settings, cache_dir=str(tmp_path))
    qtbot.addWidget(dialog)
    emitted: list[str] = []
    dialog.languageChanged.connect(emitted.append)

    dialog.language_combo.setCurrentIndex(
        dialog.language_combo.findData("fr")
    )
    dialog.accept()

    assert emitted == ["fr"]


def test_settings_dialog_does_not_emit_when_language_unchanged(
    qtbot, settings, tmp_path
):
    settings.language = "fr"
    dialog = SettingsDialog(settings, cache_dir=str(tmp_path))
    qtbot.addWidget(dialog)
    emitted: list[str] = []
    dialog.languageChanged.connect(emitted.append)

    dialog.accept()

    assert emitted == []


def test_settings_dialog_retranslate_ui_updates_labels(qtbot, settings, tmp_path):
    dialog = SettingsDialog(settings, cache_dir=str(tmp_path))
    qtbot.addWidget(dialog)

    i18n.install_translators(QApplication.instance(), "fr")
    dialog.retranslate_ui()

    assert dialog.windowTitle() == "Réglages"
    assert dialog._language_label.text() == "Langue"
    assert dialog._model_folder_label.text() == "Dossier des modèles"
    assert dialog.browse_button.text() == "Parcourir…"
    assert dialog.clear_button.text() == "Vider le cache"


def test_drop_zone_retranslate_ui_updates_label(qtbot, app):
    zone = DropZone()
    qtbot.addWidget(zone)
    assert zone.label.text() == "Drop an audio file here"

    i18n.install_translators(app, "fr")
    zone.retranslate_ui()
    assert zone.label.text() == "Déposez un fichier audio ici"

    zone.set_file("/x/song.wav")
    assert "song.wav" in zone.label.text()
    zone.retranslate_ui()
    assert "song.wav" in zone.label.text()
