"""Language resolution and Qt translator management.

Keeps the mapping between the stored language preference and the Qt
translation files bundled with the application. The current translator is
held in a module-level reference so it is not garbage-collected while Qt
still uses it.
"""

import sys
from pathlib import Path

from PySide6.QtCore import QLocale, QTranslator

from separateur_de_stems.ui import paths

__all__ = [
    "available_languages",
    "i18n_dir",
    "resolve_language",
    "install_translators",
]

_SUPPORTED = ["system", "fr"]
_TRANSLATION_BASENAME = "stem_separator_fr"

_current_translator: QTranslator | None = None


def available_languages() -> list[str]:
    """Language choices offered in the settings."""
    return list(_SUPPORTED)


def i18n_dir() -> Path:
    """Directory holding the compiled translation files."""
    if paths.is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if not meipass:
            return Path(__file__).resolve().parent / "i18n"
        return Path(meipass) / "separateur_de_stems" / "ui" / "i18n"
    return Path(__file__).resolve().parent / "i18n"


def resolve_language(setting: str) -> str | None:
    """Resolve a stored preference to a concrete language, or None for English."""
    if setting == "fr":
        return "fr"
    if setting == "system":
        if QLocale.system().language() == QLocale.Language.French:
            return "fr"
        return None
    return None


def install_translators(app, setting: str) -> str:
    """Install the translator matching ``setting``; return the active language."""
    global _current_translator

    if _current_translator is not None:
        app.removeTranslator(_current_translator)
        _current_translator = None

    resolved = resolve_language(setting)
    if resolved == "fr":
        translator = QTranslator()
        qm_path = i18n_dir() / f"{_TRANSLATION_BASENAME}.qm"
        if qm_path.is_file() and translator.load(str(qm_path)):
            app.installTranslator(translator)
            _current_translator = translator
            return "fr"

    return "en"
