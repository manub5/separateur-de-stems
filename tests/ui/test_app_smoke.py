"""Application smoke tests.

Prove that the application starts offscreen without running any inference,
touching the network or blocking on an infinite event loop. ``Settings`` uses
an isolated organization/application pair so the real user configuration is
never read or written.
"""

import pytest
from PySide6.QtWidgets import QApplication

from separateur_de_stems.ui import app as app_module
from separateur_de_stems.ui.app import build_parser
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


@pytest.fixture(autouse=True)
def restore_translators():
    """Reset the module-level translator after each test."""
    yield
    app = QApplication.instance()
    if app is not None:
        app_module.i18n.install_translators(app, "en")


def test_main_window_constructs_with_isolated_settings(qtbot, settings):
    window = MainWindow(settings=settings)
    qtbot.addWidget(window)

    assert window.windowTitle()
    assert window.drop_zone is not None
    assert window.output_edit is not None
    assert window.separate_button is not None
    assert window.progress_bar is not None
    assert window.log_view is not None
    assert set(window.stem_checkboxes) == {
        "vocals",
        "instrumental",
        "drums",
        "bass",
        "guitar",
        "piano",
    }


def test_build_parser_file_is_optional():
    parser = build_parser()

    assert parser.parse_args([]).file is None
    assert parser.parse_args(["--file", "song.wav"]).file == "song.wav"


def test_main_does_not_block(qtbot, settings, monkeypatch):
    """``main([])`` returns the exec result without running a blocking loop.

    ``QApplication.exec`` is replaced by a stub so no real event loop is
    started here. Calling the shared application's ``quit`` would corrupt the
    ``QApplication`` for every later test, so the loop must never run.
    """
    monkeypatch.setattr(app_module, "Settings", lambda: settings)
    monkeypatch.setattr(QApplication, "exec", lambda self: 0)

    exit_code = app_module.main([])

    assert exit_code == 0


def test_main_installs_translators_with_settings_language(
    qtbot, settings, monkeypatch
):
    """``main`` installs the translator for the language stored in Settings."""
    settings.language = "fr"
    calls = []

    def spy(app, setting):
        calls.append(setting)
        return "fr"

    monkeypatch.setattr(app_module, "Settings", lambda: settings)
    monkeypatch.setattr(app_module.i18n, "install_translators", spy)
    monkeypatch.setattr(QApplication, "exec", lambda self: 0)

    exit_code = app_module.main([])

    assert exit_code == 0
    assert calls == ["fr"]


def test_main_does_not_crash_with_unknown_language(qtbot, settings, monkeypatch):
    """An unknown stored language falls back safely at startup."""
    settings.language = "de"
    calls = []

    def spy(app, setting):
        calls.append(setting)
        return "en"

    monkeypatch.setattr(app_module, "Settings", lambda: settings)
    monkeypatch.setattr(app_module.i18n, "install_translators", spy)
    monkeypatch.setattr(QApplication, "exec", lambda self: 0)

    exit_code = app_module.main([])

    assert exit_code == 0
    assert calls == ["de"]


def test_main_calls_ensure_bundled_ffmpeg(qtbot, settings, monkeypatch):
    """``main`` defensively exposes the bundled ffmpeg at startup."""
    calls = []
    monkeypatch.setattr(app_module, "Settings", lambda: settings)
    monkeypatch.setattr(
        app_module, "ensure_bundled_ffmpeg_on_path", lambda: calls.append(True)
    )
    monkeypatch.setattr(QApplication, "exec", lambda self: 0)

    exit_code = app_module.main([])

    assert exit_code == 0
    assert calls == [True]


def test_main_help_exits_zero_without_crash(capsys):
    """``--help`` prints usage and never raises."""
    with pytest.raises(SystemExit) as excinfo:
        app_module.main(["--help"])

    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert "separateur-de-stems-ui" in captured.out
