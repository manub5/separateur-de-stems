"""Settings dialog.

A small ``QDialog`` exposing the model directory, the interface language and a
button clearing the download cache. ``cache_dir`` is injectable so tests can
point at a temporary directory instead of the real cache.
"""

import shutil
from pathlib import Path

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

_LANGUAGES = (
    ("system", "System"),
    ("en", "English"),
    ("fr", "Français"),
)


class SettingsDialog(QDialog):
    """Edit the persisted preferences and clear the model cache."""

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
        browse_button = QPushButton(self.tr("Browse…"), self)
        browse_button.clicked.connect(self._choose_model_dir)

        model_row = QHBoxLayout()
        model_row.addWidget(self.model_dir_edit)
        model_row.addWidget(browse_button)

        self.language_combo = QComboBox(self)
        for value, label in _LANGUAGES:
            self.language_combo.addItem(self.tr(label), value)

        clear_button = QPushButton(self.tr("Clear cache"), self)
        clear_button.clicked.connect(self._clear_cache)

        form = QFormLayout()
        form.addRow(self.tr("Model folder"), model_row)
        form.addRow(self.tr("Language"), self.language_combo)

        self._message_label = QLabel("", self)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(clear_button)
        layout.addWidget(self._message_label)
        layout.addWidget(buttons)

        self._load()

    # -- population -------------------------------------------------------

    def _load(self) -> None:
        self.model_dir_edit.setText(self._settings.model_dir)
        index = self.language_combo.findData(self._settings.language)
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
        self._settings.model_dir = self.model_dir_edit.text().strip()
        self._settings.language = self.language_combo.currentData()
        self._settings.sync()
        super().accept()

    def reject(self) -> None:
        super().reject()
