"""Settings dialog.

A small ``QDialog`` exposing the model directory, the interface language and a
button clearing the download cache. ``cache_dir`` is injectable so tests can
point at a temporary directory instead of the real cache.
"""

import shutil
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from separateur_de_stems.ui.paths import default_cache_dir
from separateur_de_stems.ui.settings import Settings

__all__ = ["SettingsDialog"]


class SettingsDialog(QDialog):
    """Edit the persisted preferences and clear the model cache."""

    languageChanged = Signal(str)

    def __init__(
        self,
        settings: Settings,
        cache_dir: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._cache_dir = (
            cache_dir if cache_dir is not None else default_cache_dir()
        )

        self.setWindowTitle(self.tr("Settings"))

        self.model_dir_edit = QLineEdit(self)
        self.browse_button = QPushButton(self.tr("Browse…"), self)
        self.browse_button.clicked.connect(self._choose_model_dir)

        model_row = QHBoxLayout()
        model_row.addWidget(self.model_dir_edit)
        model_row.addWidget(self.browse_button)

        self.language_combo = QComboBox(self)

        self.clear_button = QPushButton(self.tr("Clear cache"), self)
        self.clear_button.clicked.connect(self._clear_cache)

        self._model_folder_label = QLabel(self.tr("Model folder"), self)
        self._language_label = QLabel(self.tr("Language"), self)

        self._form = QFormLayout()
        self._form.addRow(self._model_folder_label, model_row)
        self._form.addRow(self._language_label, self.language_combo)

        self._message_label = QLabel("", self)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(self._form)
        layout.addWidget(self.clear_button)
        layout.addWidget(self._message_label)
        layout.addWidget(buttons)

        self._populate_languages()
        self._load()

    # -- population -------------------------------------------------------

    def _populate_languages(self) -> None:
        """Fill the language combo with freshly translated labels."""
        self.language_combo.clear()
        for value, label in (
            ("system", self.tr("System")),
            ("en", self.tr("English")),
            ("fr", self.tr("Français")),
        ):
            self.language_combo.addItem(label, value)

    def _load(self) -> None:
        self.model_dir_edit.setText(self._settings.model_dir)
        index = self.language_combo.findData(self._settings.language)
        self.language_combo.setCurrentIndex(index if index >= 0 else 0)

    def retranslate_ui(self) -> None:
        """Reapply every translated string after a language change."""
        current = self.language_combo.currentData()
        self.setWindowTitle(self.tr("Settings"))
        self._model_folder_label.setText(self.tr("Model folder"))
        self._language_label.setText(self.tr("Language"))
        self.browse_button.setText(self.tr("Browse…"))
        self.clear_button.setText(self.tr("Clear cache"))
        self._populate_languages()
        index = self.language_combo.findData(current)
        self.language_combo.setCurrentIndex(index if index >= 0 else 0)

    # -- actions ----------------------------------------------------------

    def _choose_model_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, self.tr("Choose model folder"), self.model_dir_edit.text()
        )
        if path:
            self.model_dir_edit.setText(path)

    def _clear_cache(self) -> None:
        if not self._ask_clear_confirmation():
            return
        self._message_label.setText(self._purge_cache())

    def _ask_clear_confirmation(self) -> bool:
        answer = QMessageBox.question(
            self,
            self.tr("Clear cache"),
            self.tr("Delete every cached model file?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _purge_cache(self) -> str:
        """Delete the cache contents, never the root directory itself."""
        root = Path(self._cache_dir)
        if not root.is_dir():
            return self.tr("Nothing to clear")
        removed = 0
        for entry in root.iterdir():
            try:
                if entry.is_dir() and not entry.is_symlink():
                    shutil.rmtree(entry)
                else:
                    entry.unlink()
                removed += 1
            except OSError:
                continue
        if removed == 0:
            return self.tr("Nothing to clear")
        return self.tr("Cache cleared")

    # -- QDialog ----------------------------------------------------------

    def accept(self) -> None:
        previous = self._settings.language
        self._settings.model_dir = self.model_dir_edit.text().strip()
        language = self.language_combo.currentData()
        self._settings.language = language
        self._settings.sync()
        if language != previous:
            self.languageChanged.emit(language)
        super().accept()

    def reject(self) -> None:
        super().reject()
