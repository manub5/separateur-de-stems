"""Qt worker thread driving the subprocess separator.

Translates the status of a ``SubprocessSeparator`` into Qt signals so the
interface can stay responsive and cancellable. This module depends on
``QtCore`` only: no widget is imported here.
"""

import multiprocessing
import threading

from PySide6.QtCore import QThread, Signal

from separateur_de_stems.core.process import SubprocessSeparator

__all__ = ["SeparationWorker"]

_POLL_TIMEOUT = 0.1


def _create_progress_queue():
    """Build a spawn-safe queue to carry progress out of the child process."""
    return multiprocessing.get_context("spawn").Queue()


class SeparationWorker(QThread):
    """Run a stem separation in a background thread.

    Signals:
        progress: ``(percent, message)`` updates reported by the runner.
        finished: the raw ``{stem: path}`` mapping on success.
        failed: a human-readable error message.
        cancelled: emitted instead of ``finished``/``failed`` on cancel.
    """

    progress = Signal(int, str)
    finished = Signal(dict)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(
        self,
        input_path,
        stems,
        output_dir,
        model_dir,
        separator_factory=None,
        progress_queue=None,
        parent=None,
    ):
        super().__init__(parent)
        self._input_path = input_path
        self._stems = set(stems)
        self._output_dir = output_dir
        self._model_dir = model_dir
        self._separator_factory = separator_factory
        self._owns_progress_queue = progress_queue is None
        self._progress_queue = (
            _create_progress_queue() if self._owns_progress_queue else progress_queue
        )

        self._cancel_requested = threading.Event()
        self._separator = None
        self._lock = threading.Lock()

    def request_cancel(self) -> None:
        """Ask for cancellation from any thread; safe to call repeatedly."""
        self._cancel_requested.set()
        with self._lock:
            separator = self._separator
        if separator is not None:
            cancel = getattr(separator, "cancel", None)
            if cancel is not None:
                try:
                    cancel()
                except Exception:  # noqa: BLE001
                    pass

    def run(self) -> None:
        """Thread body: normal errors become ``failed``, nothing escapes."""
        try:
            self._run_separation()
        except Exception as error:  # noqa: BLE001
            self.failed.emit(self._format_error(error))
        finally:
            self._close_owned_progress_queue()

    def _close_owned_progress_queue(self) -> None:
        """Best-effort close of a queue this worker created itself.

        A caller-provided queue is never touched; a queue already closed by
        the runner makes ``close()`` a harmless no-op inside the guard.
        """
        if not self._owns_progress_queue:
            return
        queue = self._progress_queue
        if queue is None:
            return
        try:
            queue.close()
        except Exception:  # noqa: BLE001
            pass

    def _run_separation(self) -> None:
        if self._cancel_requested.is_set():
            self.cancelled.emit()
            return

        separator = self._build_separator()
        with self._lock:
            self._separator = separator

        separator.start(self._input_path, self._stems)

        while True:
            outcome = separator.poll(timeout=_POLL_TIMEOUT)
            self._emit_progress(separator)
            if outcome is None:
                if self._cancel_requested.is_set():
                    separator.cancel()
                continue

            status, payload = outcome
            if status == "cancelled":
                self.cancelled.emit()
            elif status == "error":
                self.failed.emit(str(payload))
            else:
                self.finished.emit(dict(payload or {}))
            return

    def _build_separator(self):
        factory = self._separator_factory
        if factory is not None:
            return factory(
                engine_kwargs={
                    "model_dir": self._model_dir,
                    "output_dir": self._output_dir,
                },
                progress_queue=self._progress_queue,
            )
        return SubprocessSeparator(
            engine_kwargs={
                "model_dir": self._model_dir,
                "output_dir": self._output_dir,
            },
            progress_queue=self._progress_queue,
        )

    def _emit_progress(self, separator) -> None:
        poll_progress = getattr(separator, "poll_progress", None)
        if poll_progress is None:
            return
        try:
            messages = poll_progress()
        except Exception:  # noqa: BLE001
            return
        for message in messages or ():
            try:
                percent, stage = message
            except (TypeError, ValueError):
                continue
            self.progress.emit(int(percent), str(stage))

    @staticmethod
    def _format_error(error) -> str:
        message = str(error)
        if not message:
            message = error.__class__.__name__
        return message
