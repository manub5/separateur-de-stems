"""Integration tests for the compiled French catalog.

Installs the real ``.qm`` catalog through the production code path and checks
that concrete UI strings change to French and revert to their English sources.
Qt runs in offscreen mode and each test restores English on teardown.
"""

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from separateur_de_stems.ui import i18n

_CASES = [
    ("MainWindow", "Done", "Terminé"),
    ("MainWindow", "Separate", "Séparer"),
    ("MainWindow", "Cancel", "Annuler"),
    ("DropZone", "Drop an audio file here", "Déposez un fichier audio ici"),
    ("SettingsDialog", "Language", "Langue"),
    ("SettingsDialog", "System", "Système"),
    ("SettingsDialog", "English", "Anglais"),
    ("SettingsDialog", "Français", "Français"),
]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def restore_english(app):
    yield
    i18n.install_translators(app, "en")


def test_french_install_changes_real_strings(app):
    assert i18n.install_translators(app, "fr") == "fr"

    changed = 0
    for context, source, expected in _CASES:
        translated = QCoreApplication.translate(context, source)
        assert translated == expected
        if translated != source:
            changed += 1

    assert changed >= 3


@pytest.mark.parametrize("context,source,expected", _CASES)
def test_french_catalog_translates_known_strings(app, context, source, expected):
    assert i18n.install_translators(app, "fr") == "fr"
    assert QCoreApplication.translate(context, source) == expected


def test_english_restores_source_strings(app):
    i18n.install_translators(app, "fr")

    assert i18n.install_translators(app, "en") == "en"
    for context, source, _expected in _CASES:
        assert QCoreApplication.translate(context, source) == source
