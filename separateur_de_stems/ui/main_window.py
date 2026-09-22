"""Main application window.

A compact single-window interface composing the drag and drop zone, the stem
selection, the output directory picker, the progress/history widgets and the
menu bar. Separation runs in a ``SeparationWorker`` thread; the window only
bridges its signals to the widgets and never blocks the event loop.

The window deliberately holds no separation logic: the worker returns the raw
``{stem: path}`` mapping and this module groups the results into a per-song
sub-directory, exporting a 24-bit WAV and a 320 kb/s MP3 for every stem.
"""

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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

from separateur_de_stems.core.export import to_mp3_320, to_wav24
from separateur_de_stems.core.models import SUPPORTED_EXTENSIONS
from separateur_de_stems.core.naming import sanitize, stem_filename
from separateur_de_stems.ui.drop_zone import DropZone
from separateur_de_stems.ui.paths import default_model_dir, default_output_dir
from separateur_de_stems.ui.settings import Settings
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
        self._run_stems: set[str] | None = None
        self._pre_run_files: set[str] | None = None

        self.setWindowTitle(self.tr("Stem Separator"))
        self._build_menu()
        self._build_ui()
        self._restore_settings()
        self._update_controls()

    # -- construction -----------------------------------------------------

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu(self.tr("File"))

        open_action = file_menu.addAction(self.tr("Open…"))
        open_action.triggered.connect(self._choose_input_file)

        file_menu.addSeparator()
        quit_action = file_menu.addAction(self.tr("Quit"))
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)

        edit_menu = self.menuBar().addMenu(self.tr("Edit"))
        settings_action = edit_menu.addAction(self.tr("Settings…"))
        settings_action.triggered.connect(self.open_settings)

        help_menu = self.menuBar().addMenu(self.tr("Help"))
        about_action = help_menu.addAction(self.tr("About"))
        about_action.triggered.connect(self._show_about)

    def _build_ui(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)

        self.drop_zone = DropZone(central)
        self.drop_zone.fileDropped.connect(self.open_file)
        self.drop_zone.fileRejected.connect(self._on_file_rejected)
        layout.addWidget(self.drop_zone)

        open_button = QPushButton(self.tr("Open…"), central)
        open_button.clicked.connect(self._choose_input_file)
        layout.addWidget(open_button)

        stems_label = QLabel(self.tr("Stems to extract"), central)
        layout.addWidget(stems_label)

        self.stem_checkboxes: dict[str, QCheckBox] = {}
        stems_layout = QHBoxLayout()
        for stem in _CANONICAL_STEMS:
            checkbox = QCheckBox(self._stem_label(stem), central)
            checkbox.stateChanged.connect(self._update_controls)
            self.stem_checkboxes[stem] = checkbox
            stems_layout.addWidget(checkbox)
        layout.addLayout(stems_layout)

        output_label = QLabel(self.tr("Output folder"), central)
        layout.addWidget(output_label)

        output_layout = QHBoxLayout()
        self.output_edit = QLineEdit(central)
        self.output_edit.textChanged.connect(self._update_controls)
        output_layout.addWidget(self.output_edit)

        choose_button = QPushButton(self.tr("Choose…"), central)
        choose_button.clicked.connect(self._choose_output_dir)
        output_layout.addWidget(choose_button)
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
        if self._running:
            return
        input_path = self._input_path
        stems = self.selected_stems()
        output_dir = self.output_edit.text().strip()
        if not input_path or not stems or not output_dir:
            return

        self._settings.output_dir = output_dir

        self._run_stems = set(stems)
        self._pre_run_files = self._snapshot_files(output_dir)

        worker = self._worker_factory(
            input_path, stems, output_dir, default_model_dir()
        )
        worker.progress.connect(self.on_progress)
        worker.finished.connect(self.on_finished)
        worker.failed.connect(self.on_failed)
        worker.cancelled.connect(self.on_cancelled)

        self._worker = worker
        self._set_running_state(True)
        self._log(self.tr("Starting separation…"))
        worker.start()

    def cancel_separation(self) -> None:
        if self._worker is not None:
            self._worker.request_cancel()

    # -- slots ------------------------------------------------------------

    def on_progress(self, percent: int, message: str) -> None:
        self.progress_bar.setValue(int(percent))
        if message:
            self.status_label.setText(message)

    def on_finished(self, outputs: dict) -> None:
        try:
            exported = self._export_outputs(outputs)
        except Exception as error:  # noqa: BLE001
            self.on_failed(str(error))
            return

        self._set_running_state(False)
        self.progress_bar.setValue(100)
        self.status_label.setText(self.tr("Done"))
        for path in exported:
            self._log(path)
        self._offer_open_folder(
            self.output_edit.text().strip()
        )

    def on_failed(self, message: str) -> None:
        self._set_running_state(False)
        self.status_label.setText(self.tr("Failed"))
        self._log(self.tr("Error: {message}").format(message=message))

    def on_cancelled(self) -> None:
        self._cleanup_run_partials()
        self._set_running_state(False)
        self.status_label.setText(self.tr("Cancelled"))
        self._log(self.tr("Cancelled"))

    def open_settings(self) -> None:
        """Placeholder until the settings dialog lands in Task 8."""

    # -- export -----------------------------------------------------------

    def _export_outputs(self, outputs: dict) -> list[str]:
        input_path = self._input_path
        if not input_path:
            return []
        output_dir = self.output_edit.text().strip()
        song = os.path.splitext(os.path.basename(input_path))[0]
        song_dir = os.path.join(output_dir, sanitize(song))

        requested = (
            self._run_stems
            if self._run_stems is not None
            else self.selected_stems()
        )

        exported: list[str] = []
        intermediates: list[str] = []
        for stem in sorted(requested & outputs.keys()):
            source = outputs[stem]
            if not Path(source).is_file():
                raise FileNotFoundError(source)
            intermediates.append(source)
            wav_path = stem_filename(input_path, stem, "wav", song_dir)
            to_wav24(source, wav_path)
            exported.append(wav_path)
            mp3_path = stem_filename(input_path, stem, "mp3", song_dir)
            to_mp3_320(wav_path, mp3_path)
            exported.append(mp3_path)

        self._remove_intermediates(intermediates, exported, output_dir)
        return exported

    @staticmethod
    def _remove_intermediates(
        intermediates: list[str], exported: list[str], output_dir: str
    ) -> None:
        """Delete unexported intermediates that live under ``output_dir``.

        A file outside the output folder is never touched, so a caller-chosen
        engine output location or a user file is preserved.
        """
        protected = {str(Path(path).resolve()) for path in exported}
        try:
            root = Path(output_dir).resolve()
        except OSError:
            return
        for path in intermediates:
            try:
                link = Path(path)
                resolved = link.resolve()
                if resolved in protected:
                    continue
                if not resolved.is_relative_to(root):
                    continue
                link.unlink()
            except OSError:
                pass

    def _cleanup_run_partials(self) -> None:
        """Best-effort removal of files created by the current run.

        Only files under the output folder that did not exist when the run
        started are removed, so pre-existing user files are never deleted.
        """
        if self._pre_run_files is None:
            return
        output_dir = self.output_edit.text().strip()
        if not output_dir:
            return
        for path in self._snapshot_files(output_dir) - self._pre_run_files:
            try:
                Path(path).unlink()
            except OSError:
                pass
        self._pre_run_files = None

    @staticmethod
    def _snapshot_files(output_dir: str) -> set[str]:
        """Absolute paths of every file currently under ``output_dir``.

        Symlinks are recorded as links (not resolved) so a later cleanup
        unlinks the link itself and never its target.
        """
        root = Path(output_dir)
        if not root.is_dir():
            return set()
        files: set[str] = set()
        try:
            for candidate in root.rglob("*"):
                if candidate.is_file():
                    files.add(str(candidate.absolute()))
        except OSError:
            return files
        return files

    # -- helpers ----------------------------------------------------------

    def _default_worker_factory(self, input_path, stems, output_dir, model_dir):
        return SeparationWorker(input_path, stems, output_dir, model_dir)

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

    def _set_running_state(self, running: bool) -> None:
        self._running = running
        self.separate_button.setText(
            self.tr("Cancel") if running else self.tr("Separate")
        )
        self.drop_zone.setEnabled(not running)
        self.output_edit.setEnabled(not running)
        for checkbox in self.stem_checkboxes.values():
            checkbox.setEnabled(not running)
        # Keep the worker reference: the QThread is still unwinding ``run()``
        # when it emits its terminal signal, so dropping it here could destroy
        # a live thread. It is replaced on the next ``start_separation``.
        self._update_controls()

    def _update_controls(self) -> None:
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
        lowered = path.lower()
        return any(lowered.endswith(extension) for extension in SUPPORTED_EXTENSIONS)

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
