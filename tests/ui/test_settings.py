"""Tests for QSettings-backed preferences.

The tests use an isolated organization/application pair and clear the
backing store before and after each test so the real user configuration is
never read or written.
"""

import pytest

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


def test_defaults(settings):
    assert settings.language == "system"
    assert settings.last_input_dir == ""
    assert settings.output_dir == ""
    assert settings.model_dir == ""
    assert settings.default_stems == ["vocals", "instrumental"]


def test_language_roundtrip(settings):
    settings.language = "fr"
    assert settings.language == "fr"


def test_stems_roundtrip(settings):
    settings.default_stems = ["vocals", "drums", "bass"]
    assert settings.default_stems == ["vocals", "drums", "bass"]


def test_output_dir_default_is_empty(settings):
    assert settings.output_dir == ""


def test_output_dir_roundtrip(settings):
    settings.output_dir = "/tmp/out"
    assert settings.output_dir == "/tmp/out"


def test_explicitly_empty_stems_read_back_empty(settings):
    settings.default_stems = []
    assert settings.default_stems == []


def test_sync_flushes_pending_values(settings, tmp_path):
    settings.model_dir = str(tmp_path / "models")
    settings.language = "fr"
    settings.sync()

    reopened = Settings(organization=ORG, application=APP)
    assert reopened.model_dir == str(tmp_path / "models")
    assert reopened.language == "fr"
