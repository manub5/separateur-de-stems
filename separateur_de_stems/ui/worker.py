"""Qt worker thread driving the subprocess separator.

Translates the status of a ``SubprocessSeparator`` into Qt signals so the
interface can stay responsive and cancellable. This module depends on
``QtCore`` only: no widget is imported here.
"""

import multiprocessing
import threading

from PySide6.QtCore import QThread, Signal

from separateur_de_stems.core.errors import CancelledError
from separateur_de_stems.core.pipeline import (
    _finalize_outputs as _pipeline_finalize_outputs,
)
from separateur_de_stems.core.pipeline import _rename_no_replace
from separateur_de_stems.core.process import SubprocessSeparator
from separateur_de_stems.ui.run_context import RunContext

__all__ = ["SeparationWorker"]

_POLL_TIMEOUT = 0.1


def _finalize_outputs(context, outputs, **kwargs):
    """Compatibility facade around the centralized pipeline finalizer."""
    return _pipeline_finalize_outputs(
        context, outputs, rename_publisher=_rename_no_replace, **kwargs
    )


def _raise_if_cancelled(cancel_requested) -> None:
    if cancel_requested():
        raise CancelledError("Export cancelled")


def _create_progress_queue():
    """Build a spawn-safe queue to carry progress out of the child process."""
    return multiprocessing.get_context("spawn").Queue()


class SeparationWorker(QThread):
    """Run a stem separation in a background thread.

    Signals:
        progress: ``(percent, message)`` updates reported by the runner.
        completed: final published WAV/MP3 paths on success.
        failed: a human-readable error message.
        cancelled: emitted instead of ``finished``/``failed`` on cancel.
    """

    progress = Signal(int, str)
    completed = Signal(list)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(
        self,
        context: RunContext,
        separator_factory=None,
        finalize_outputs=None,
        progress_queue=None,
        parent=None,
    ):
        super().__init__(parent)
        self._context = context
        self._separator_factory = separator_factory
        self._finalize_outputs = finalize_outputs
        self._owns_progress_queue = progress_queue is None
        self._progress_queue = (
            _create_progress_queue() if self._owns_progress_queue else progress_queue
        )

        self._cancel_requested = threading.Event()
        self._separator = None

    def request_cancel(self) -> None:
        """Record cancellation without calling potentially blocking process code."""
        self._cancel_requested.set()

    def run(self) -> None:
        """Thread body: normal errors become ``failed``, nothing escapes."""
        try:
            self._run_separation()
        except CancelledError:
            self.cancelled.emit()
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
        self._separator = separator

        separator.start(self._context.input_path, set(self._context.stems))

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
                _raise_if_cancelled(self._cancel_requested.is_set)
                if self._finalize_outputs is not None:
                    exported = self._finalize_outputs(
                        self._context,
                        dict(payload or {}),
                        cancel_requested=self._cancel_requested.is_set,
                    )
                else:
                    result = dict(payload or {})
                    missing = self._context.stems - result.keys()
                    if missing:
                        raise RuntimeError(
                            f"Missing outputs: {', '.join(sorted(missing))}"
                        )
                    exported = [
                        path
                        for stem in sorted(self._context.stems)
                        for path in result[stem]
                    ]
                self.completed.emit(exported)
            return

    def _build_separator(self):
        factory = self._separator_factory
        if factory is not None:
            return factory(
                engine_kwargs={
                    "model_dir": self._context.model_dir,
                    "output_dir": self._context.output_dir,
                    "_workspace": self._context.workspace,
                },
                progress_queue=self._progress_queue,
            )
        return SubprocessSeparator(
            engine_kwargs={
                "model_dir": self._context.model_dir,
                "output_dir": self._context.output_dir,
                "_workspace": self._context.workspace,
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
            self.progress.emit(int(percent), self._translated_stage(str(stage)))

    def _translated_stage(self, stage: str) -> str:
        messages = {
            "export.wav": self.tr("Exporting WAV…"),
            "export.mp3": self.tr("Exporting MP3…"),
            "pipeline.complete": self.tr("Finalizing…"),
        }
        return messages.get(stage, stage)

    @staticmethod
    def _format_error(error) -> str:
        message = str(error)
        if not message:
            message = error.__class__.__name__
        return message
