"""Drag and drop zone accepting local audio files.

Keeps a single selected file path and reports it through ``fileDropped``
when a supported file is dropped, or through ``fileRejected`` otherwise.
The widget only decides *which path* was chosen; format validation relies on
``core.models.SUPPORTED_EXTENSIONS`` so the catalogue stays the single source
of truth.
"""

import os

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from separateur_de_stems.core.models import is_supported_audio

__all__ = ["DropZone"]


class DropZone(QFrame):
    """A frame that accepts one local audio file through drag and drop.

    Signals:
        fileDropped: path of the first supported local file dropped.
        fileRejected: first dropped path that is not usable, or a message.
            The payload is a raw path (not a translated sentence) when a path
            exists; the interface is responsible for mapping it to a message.
    """

    fileDropped = Signal(str)
    fileRejected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_file = None

        self.setAcceptDrops(True)
        self.label = QLabel(self.tr("Drop an audio file here"), self)
        self.label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(self.label)

    def current_file(self) -> str | None:
        """Return the currently memorised file path, if any."""
        return self._current_file

    def set_file(self, path: str | None) -> None:
        """Memorise ``path`` and refresh the label (filename or prompt)."""
        self._current_file = path
        if path:
            name = os.path.basename(path)
            self.label.setText(self.tr("Selected file: {name}").format(name=name))
        else:
            self.label.setText(self.tr("Drop an audio file here"))

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        paths = [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if url.isLocalFile()
        ]
        for path in paths:
            if self._is_supported(path):
                self.set_file(path)
                self.fileDropped.emit(path)
                event.acceptProposedAction()
                return
        event.ignore()
        self.fileRejected.emit(paths[0] if paths else self.tr("Unsupported drop"))

    @staticmethod
    def _is_supported(path: str) -> bool:
        return is_supported_audio(path)
