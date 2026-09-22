"""Qt worker thread driving the subprocess separator.

Translates the status of a ``SubprocessSeparator`` into Qt signals so the
interface can stay responsive and cancellable. This module depends on
``QtCore`` only: no widget is imported here.
"""

import multiprocessing
import os
import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from separateur_de_stems.core.export import to_mp3_320, to_wav24
from separateur_de_stems.core.naming import sanitize, stem_filename
from separateur_de_stems.core.process import SubprocessSeparator
from separateur_de_stems.ui.run_context import RunContext

__all__ = ["SeparationWorker"]

_POLL_TIMEOUT = 0.1


def _finalize_outputs(
    context: RunContext,
    outputs: dict,
    wav_exporter=to_wav24,
    mp3_exporter=to_mp3_320,
) -> list[str]:
    """Stage every deliverable, then atomically publish the complete song."""
    if not outputs:
        raise RuntimeError("Separation returned no outputs")
    missing = context.stems - outputs.keys()
    if missing:
        raise RuntimeError(f"Missing outputs: {', '.join(sorted(missing))}")

    sources = {stem: Path(outputs[stem]) for stem in context.stems}
    for source in sources.values():
        if not source.is_file():
            raise FileNotFoundError(source)

    song = sanitize(Path(context.input_path).stem)
    final_song_dir = Path(context.output_dir) / song
    if os.path.lexists(final_song_dir):
        raise FileExistsError(f"Output already exists: {final_song_dir}")

    staged_song_dir = Path(context.workspace) / "deliverables" / song
    exported: list[Path] = []
    for stem in sorted(context.stems):
        wav_path = Path(
            stem_filename(context.input_path, stem, "wav", str(staged_song_dir))
        )
        wav_exporter(str(sources[stem]), str(wav_path))
        exported.append(wav_path)
        mp3_path = Path(
            stem_filename(context.input_path, stem, "mp3", str(staged_song_dir))
        )
        mp3_exporter(str(wav_path), str(mp3_path))
        exported.append(mp3_path)

    missing_deliverables = [path for path in exported if not path.is_file()]
    if missing_deliverables:
        raise RuntimeError(f"Export did not create: {missing_deliverables[0]}")
    if os.path.lexists(final_song_dir):
        raise FileExistsError(f"Output already exists: {final_song_dir}")
    staged_song_dir.rename(final_song_dir)
    return [str(final_song_dir / path.name) for path in exported]


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
        self._finalize_outputs = finalize_outputs or _finalize_outputs
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
                exported = self._finalize_outputs(
                    self._context, dict(payload or {})
                )
                self.completed.emit(exported)
            return

    def _build_separator(self):
        factory = self._separator_factory
        if factory is not None:
            return factory(
                engine_kwargs={
                    "model_dir": self._context.model_dir,
                    "output_dir": self._context.workspace,
                },
                progress_queue=self._progress_queue,
            )
        return SubprocessSeparator(
            engine_kwargs={
                "model_dir": self._context.model_dir,
                "output_dir": self._context.workspace,
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
