"""Application preferences backed by QSettings.

Thin typed wrapper around ``QSettings`` so the rest of the UI never deals
with raw string keys. The organization/application names are injectable so
tests can use an isolated store and keep the real user configuration clean.
"""

from PySide6.QtCore import QSettings

__all__ = ["Settings"]

_DEFAULT_STEMS = ["vocals", "instrumental"]
_STEMS_SEPARATOR = ","


class Settings:
    """Typed preferences stored through ``QSettings``."""

    def __init__(
        self,
        organization: str = "StemSeparator",
        application: str = "StemSeparator",
    ) -> None:
        self._settings = QSettings(organization, application)

    @property
    def language(self) -> str:
        value = self._settings.value("language", "system")
        return str(value)

    @language.setter
    def language(self, value: str) -> None:
        self._settings.setValue("language", value)

    @property
    def last_input_dir(self) -> str:
        value = self._settings.value("paths/last_input_dir", "")
        return str(value)

    @last_input_dir.setter
    def last_input_dir(self, value: str) -> None:
        self._settings.setValue("paths/last_input_dir", value)

    @property
    def output_dir(self) -> str:
        value = self._settings.value("paths/output_dir", "")
        return str(value)

    @output_dir.setter
    def output_dir(self, value: str) -> None:
        self._settings.setValue("paths/output_dir", value)

    @property
    def model_dir(self) -> str:
        value = self._settings.value("paths/model_dir", "")
        return str(value)

    @model_dir.setter
    def model_dir(self, value: str) -> None:
        self._settings.setValue("paths/model_dir", value)

    @property
    def default_stems(self) -> list[str]:
        if not self._settings.contains("stems/default"):
            return list(_DEFAULT_STEMS)
        raw = str(self._settings.value("stems/default", ""))
        if raw == "":
            return []
        return raw.split(_STEMS_SEPARATOR)

    @default_stems.setter
    def default_stems(self, value: list[str]) -> None:
        self._settings.setValue("stems/default", _STEMS_SEPARATOR.join(value))

    def clear(self) -> None:
        """Remove every stored preference."""
        self._settings.clear()
        self._settings.sync()
