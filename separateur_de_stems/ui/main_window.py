"""Main application window.

A compact single-window interface composing the drag and drop zone, the stem
selection, the output directory picker, the progress/history widgets and the
menu bar. Separation runs in a ``SeparationWorker`` thread; the window only
bridges its signals to the widgets and never blocks the event loop.

The window deliberately holds no separation or export logic: the worker stages
and publishes complete deliverables before reporting their final paths.
"""

import os
import shutil
import tempfile
from pathlib import Path

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from separateur_de_stems.core.models import is_supported_audio
from separateur_de_stems.ui import i18n
from separateur_de_stems.ui.drop_zone import DropZone
from separateur_de_stems.ui.paths import default_model_dir, default_output_dir
from separateur_de_stems.ui.run_context import RunContext
from separateur_de_stems.ui.settings import Settings
from separateur_de_stems.ui.settings_dialog import SettingsDialog
from separateur_de_stems.ui.worker import SeparationWorker

__all__ = ["MainWindow"]

_CANONICAL_STEMS = ("vocals", "instrumental", "drums", "bass", "guitar", "piano")


class MainWindow(QMainWindow):
    """Single-window front-end for the stem separator."""

    def __init__(self, settings: Settings | None = None, worker_factory=None):
        super().__init__()
        self._settings = settings if settings is not None else Settings()
        self._worker_factory = worker_factory or self._default_worker_factory
        self._worker = None
        self._input_path: str | None = None
        self._running = False
        self._exporting = False
        self._run_context: RunContext | None = None
        self._terminal_received = False
        self._close_pending = False

        self.setWindowTitle(self.tr("Stem Separator"))
        self._build_menu()
        self._build_ui()
        self._restore_settings()
        self._update_controls()

    # -- construction -----------------------------------------------------

    def _build_menu(self) -> None:
        self._file_menu = self.menuBar().addMenu(self.tr("File"))

        self._open_action = self._file_menu.addAction(self.tr("Open…"))
        self._open_action.triggered.connect(self._choose_input_file)

        self._file_menu.addSeparator()
        self._quit_action = self._file_menu.addAction(self.tr("Quit"))
        self._quit_action.setShortcut("Ctrl+Q")
        self._quit_action.triggered.connect(self.close)

        self._edit_menu = self.menuBar().addMenu(self.tr("Edit"))
        self._settings_action = self._edit_menu.addAction(self.tr("Settings…"))
        self._settings_action.triggered.connect(self.open_settings)

        self._help_menu = self.menuBar().addMenu(self.tr("Help"))
        self._about_action = self._help_menu.addAction(self.tr("About"))
        self._about_action.triggered.connect(self._show_about)

    def _build_ui(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)

        self.drop_zone = DropZone(central)
        self.drop_zone.fileDropped.connect(self.open_file)
        self.drop_zone.fileRejected.connect(self._on_file_rejected)
        layout.addWidget(self.drop_zone)

        self.open_button = QPushButton(self.tr("Open…"), central)
        self.open_button.clicked.connect(self._choose_input_file)
        layout.addWidget(self.open_button)

        self.stems_label = QLabel(self.tr("Stems to extract"), central)
        layout.addWidget(self.stems_label)

        self.stem_checkboxes: dict[str, QCheckBox] = {}
        stems_layout = QHBoxLayout()
        for stem in _CANONICAL_STEMS:
            checkbox = QCheckBox(self._stem_label(stem), central)
            checkbox.stateChanged.connect(self._update_controls)
            self.stem_checkboxes[stem] = checkbox
            stems_layout.addWidget(checkbox)
        layout.addLayout(stems_layout)

        self.output_label = QLabel(self.tr("Output folder"), central)
        layout.addWidget(self.output_label)

        output_layout = QHBoxLayout()
        self.output_edit = QLineEdit(central)
        self.output_edit.textChanged.connect(self._update_controls)
        output_layout.addWidget(self.output_edit)

        self.choose_button = QPushButton(self.tr("Choose…"), central)
        self.choose_button.clicked.connect(self._choose_output_dir)
        output_layout.addWidget(self.choose_button)
        layout.addLayout(output_layout)

        self.separate_button = QPushButton(self.tr("Separate"), central)
        self.separate_button.clicked.connect(self._on_separate_clicked)
        layout.addWidget(self.separate_button)

        self.progress_bar = QProgressBar(central)
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("", central)
        layout.addWidget(self.status_label)

        self.log_view = QPlainTextEdit(central)
        self.log_view.setReadOnly(True)
        self.log_view.setFixedHeight(60)
        layout.addWidget(self.log_view)

        self.setCentralWidget(central)
        self.resize(560, 480)

    def _restore_settings(self) -> None:
        default_output = self._settings.output_dir or default_output_dir()
        self.output_edit.setText(default_output)

        enabled = set(self._settings.default_stems)
        for stem, checkbox in self.stem_checkboxes.items():
            checkbox.setChecked(stem in enabled)

    # -- public API -------------------------------------------------------

    def open_file(self, path: str) -> None:
        """Validate ``path`` and memorise it without reading the audio."""
        if self._running:
            return
        if not self._is_supported(path):
            self._log(self.tr("Unsupported file: {name}").format(
                name=os.path.basename(path)
            ))
            return
        self._input_path = path
        self.drop_zone.set_file(path)
        self._log(self.tr("Selected file: {name}").format(
            name=os.path.basename(path)
        ))
        self._update_controls()

    def current_file(self) -> str | None:
        return self._input_path

    def selected_stems(self) -> set[str]:
        return {
            stem
            for stem, checkbox in self.stem_checkboxes.items()
            if checkbox.isChecked()
        }

    def start_separation(self) -> None:
        if self._running or self._exporting:
            return
        input_path = self._input_path
        stems = self.selected_stems()
        output_dir = self.output_edit.text().strip()
        if not input_path or not stems or not output_dir:
            return

        model_dir = self._settings.model_dir.strip() or default_model_dir()
        error = self._validate_run_paths(input_path, output_dir, model_dir)
        if error:
            self.on_failed(error)
            return

        self._settings.output_dir = output_dir

        workspace = tempfile.mkdtemp(prefix=".stem-separator-", dir=output_dir)
        self._run_context = RunContext(
            input_path=input_path,
            output_dir=output_dir,
            model_dir=model_dir,
            stems=frozenset(stems),
            workspace=workspace,
        )
        self._terminal_received = False

        try:
            worker = self._worker_factory(self._run_context)
            worker.progress.connect(self.on_progress)
            worker.completed.connect(self.on_finished)
            worker.failed.connect(self.on_failed)
            worker.cancelled.connect(self.on_cancelled)
            worker.finished.connect(self._on_thread_finished)

            self._worker = worker
            self._set_running_state(True)
            self._log(self.tr("Starting separation…"))
            worker.start()
        except Exception as error:  # noqa: BLE001
            if self._worker is not None:
                self._worker.deleteLater()
            self._cleanup_workspace()
            self._worker = None
            self._run_context = None
            self._set_running_state(False)
            self.on_failed(str(error))

    def cancel_separation(self) -> None:
        # Cancellation remains a non-blocking request throughout worker work.
        if self._exporting:
            return
        if self._worker is not None:
            self._worker.request_cancel()

    # -- slots ------------------------------------------------------------

    def on_progress(self, percent: int, message: str) -> None:
        self.progress_bar.setValue(int(percent))
        if message:
            self.status_label.setText(message)

    def on_finished(self, exported: list[str]) -> None:
        self._terminal_received = True
        self.progress_bar.setValue(100)
        self.status_label.setText(self.tr("Done"))
        for path in exported:
            self._log(path)
        context = self._run_context
        if context is not None:
            self._offer_open_folder(context.output_dir)
        if self._worker is None:
            self._on_thread_finished()

    def on_failed(self, message: str) -> None:
        self._terminal_received = True
        self.status_label.setText(self.tr("Failed"))
        self._log(self.tr("Error: {message}").format(message=message))
        if self._worker is None:
            self._on_thread_finished()

    def on_cancelled(self) -> None:
        self._terminal_received = True
        self.status_label.setText(self.tr("Cancelled"))
        self._log(self.tr("Cancelled"))
        if self._worker is None:
            self._on_thread_finished()

    def open_settings(self) -> None:
        """Open the settings dialog and persist accepted values.

        A language change is applied live through ``apply_language`` so the
        window, menus and dialogs switch without a restart.
        """
        if self._running:
            return
        dialog = SettingsDialog(self._settings, parent=self)
        dialog.languageChanged.connect(self.apply_language)
        dialog.exec()

    def apply_language(self, setting: str) -> None:
        """Persist ``setting`` and install the matching translators.

        The translators are installed on the running application; Qt then
        sends a ``LanguageChange`` event to every widget, which triggers
        ``retranslate_ui`` through ``changeEvent``. The explicit call keeps
        the window consistent when no event loop is running.
        """
        self._settings.language = setting
        self._settings.sync()
        app = QApplication.instance()
        if app is not None:
            i18n.install_translators(app, setting)
        self.retranslate_ui()

    # -- translation ------------------------------------------------------

    def retranslate_ui(self) -> None:
        """Reapply every translated string after a language change.

        Safe to call when the widgets do not exist yet: each block runs only
        when the attribute has been built.
        """
        self.setWindowTitle(self.tr("Stem Separator"))
        self._retranslate_menu()
        self._retranslate_widgets()

    def _retranslate_menu(self) -> None:
        if hasattr(self, "_file_menu"):
            self._file_menu.setTitle(self.tr("File"))
            self._open_action.setText(self.tr("Open…"))
            self._quit_action.setText(self.tr("Quit"))
            self._edit_menu.setTitle(self.tr("Edit"))
            self._settings_action.setText(self.tr("Settings…"))
            self._help_menu.setTitle(self.tr("Help"))
            self._about_action.setText(self.tr("About"))

    def _retranslate_widgets(self) -> None:
        if hasattr(self, "drop_zone"):
            self.drop_zone.retranslate_ui()
        if hasattr(self, "open_button"):
            self.open_button.setText(self.tr("Open…"))
        if hasattr(self, "stems_label"):
            self.stems_label.setText(self.tr("Stems to extract"))
        if hasattr(self, "stem_checkboxes"):
            for stem, checkbox in self.stem_checkboxes.items():
                checkbox.setText(self._stem_label(stem))
        if hasattr(self, "output_label"):
            self.output_label.setText(self.tr("Output folder"))
        if hasattr(self, "choose_button"):
            self.choose_button.setText(self.tr("Choose…"))
        if hasattr(self, "separate_button"):
            self._set_button_label()

    def _set_button_label(self) -> None:
        """Refresh the separate/cancel button for the current run state."""
        if self._running and not self._exporting:
            self.separate_button.setText(self.tr("Cancel"))
        else:
            self.separate_button.setText(self.tr("Separate"))

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    # -- helpers ----------------------------------------------------------

    def _default_worker_factory(self, context: RunContext):
        return SeparationWorker(context)

    def _on_separate_clicked(self) -> None:
        if self._running:
            self.cancel_separation()
        else:
            self.start_separation()

    def _choose_input_file(self) -> None:
        start_dir = self._settings.last_input_dir or ""
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Open audio file"),
            start_dir,
            self.tr("Audio files (*.wav *.flac *.mp3 *.aif *.aiff *.m4a)"),
        )
        if path:
            self.open_file(path)
            self._settings.last_input_dir = os.path.dirname(path)

    def _choose_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, self.tr("Choose output folder"), self.output_edit.text()
        )
        if path:
            self.output_edit.setText(path)

    def _on_file_rejected(self, payload: str) -> None:
        self._log(self.tr("Unsupported file: {name}").format(
            name=os.path.basename(payload)
        ))

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            self.tr("About"),
            self.tr("Stem Separator"),
        )

    def _offer_open_folder(self, folder: str) -> None:
        """Ask, without blocking, whether to reveal the output folder."""
        if not folder:
            return
        box = QMessageBox(self)
        box.setWindowTitle(self.tr("Open output folder?"))
        box.setText(self.tr("Open the output folder?"))
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        box.accepted.connect(lambda: self._open_folder(folder))
        box.open()

    @staticmethod
    def _open_folder(folder: str) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _set_exporting_state(self, exporting: bool) -> None:
        """Mark the post-separation export phase.

        No worker is alive anymore, so the button must not read "Cancel"
        nor offer cancellation while the files are written.
        """
        self._exporting = exporting
        self._set_button_label()
        self._update_controls()

    def _set_running_state(self, running: bool) -> None:
        self._running = running
        self._set_button_label()
        self.drop_zone.setEnabled(not running)
        self.open_button.setEnabled(not running)
        self._open_action.setEnabled(not running)
        self.output_edit.setEnabled(not running)
        self.choose_button.setEnabled(not running)
        self._settings_action.setEnabled(not running)
        for checkbox in self.stem_checkboxes.values():
            checkbox.setEnabled(not running)
        # Keep the worker reference: the QThread is still unwinding ``run()``
        # when it emits its terminal signal, so dropping it here could destroy
        # a live thread. It is replaced on the next ``start_separation``.
        self._update_controls()

    def _on_thread_finished(self) -> None:
        worker = self._worker
        if worker is not None and not self._terminal_received:
            self._terminal_received = True
            self.status_label.setText(self.tr("Failed"))
            self._log(self.tr("Error: worker stopped without a terminal result"))
        self._cleanup_workspace()
        self._worker = None
        self._run_context = None
        self._set_running_state(False)
        if worker is not None:
            worker.deleteLater()
        if self._close_pending:
            self._close_pending = False
            self.close()

    def _cleanup_workspace(self) -> None:
        context = self._run_context
        if context is not None:
            shutil.rmtree(context.workspace, ignore_errors=True)

    @staticmethod
    def _validate_run_paths(
        input_path: str, output_dir: str, model_dir: str
    ) -> str | None:
        source = Path(input_path)
        if not source.is_file() or not os.access(source, os.R_OK):
            return f"Input file is not readable: {input_path}"
        destination = Path(output_dir)
        try:
            destination.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            return f"Output folder cannot be created: {error}"
        if not destination.is_dir() or not os.access(destination, os.W_OK):
            return f"Output folder is not writable: {output_dir}"
        models = Path(model_dir)
        if not models.is_dir() or not os.access(models, os.R_OK):
            return f"Model folder is not readable: {model_dir}"
        return None

    def closeEvent(self, event) -> None:
        if self._worker is not None:
            self._close_pending = True
            self.cancel_separation()
            event.ignore()
            return
        event.accept()

    def _update_controls(self) -> None:
        if self._exporting:
            self.separate_button.setEnabled(False)
            return
        if self._running:
            self.separate_button.setEnabled(True)
            return
        has_file = self._input_path is not None
        has_stem = bool(self.selected_stems())
        self.separate_button.setEnabled(has_file and has_stem)

    def _log(self, message: str) -> None:
        self.log_view.appendPlainText(message)

    @staticmethod
    def _is_supported(path: str) -> bool:
        return is_supported_audio(path)

    def _stem_label(self, stem: str) -> str:
        """Translated checkbox label for ``stem`` using literal strings."""
        labels = {
            "vocals": lambda: self.tr("Vocals"),
            "instrumental": lambda: self.tr("Instrumental"),
            "drums": lambda: self.tr("Drums"),
            "bass": lambda: self.tr("Bass"),
            "guitar": lambda: self.tr("Guitar"),
            "piano": lambda: self.tr("Piano"),
        }
        return labels[stem]()
