"""Tests for language resolution and translator loading.

The system locale of the development machine is already French, so the
"system -> English" case must mock ``QLocale.system()`` to be meaningful.
Qt is run in offscreen mode.
"""

import pytest
from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QApplication

from separateur_de_stems.ui import i18n


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_available_languages_contains_system_and_fr():
    languages = i18n.available_languages()
    assert "system" in languages
    assert "fr" in languages


def test_resolve_language_fr():
    assert i18n.resolve_language("fr") == "fr"


def test_resolve_language_en_is_none():
    assert i18n.resolve_language("en") is None


def test_resolve_language_system_french(monkeypatch):
    monkeypatch.setattr(
        QLocale,
        "system",
        staticmethod(lambda: QLocale(QLocale.Language.French)),
    )
    assert i18n.resolve_language("system") == "fr"


def test_resolve_language_system_english(monkeypatch):
    monkeypatch.setattr(
        QLocale,
        "system",
        staticmethod(lambda: QLocale(QLocale.Language.English)),
    )
    assert i18n.resolve_language("system") is None


def test_i18n_dir_contains_source_file():
    source = i18n.i18n_dir() / "stem_separator_fr.ts"
    assert source.is_file()


def test_install_translators_fr_then_en(app):
    assert i18n.install_translators(app, "fr") == "fr"
    assert i18n.install_translators(app, "en") == "en"
