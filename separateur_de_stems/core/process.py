"""Cancellable subprocess runner for stem separation.

Runs a separation worker in a killable child process so the UI thread can
request cancellation without waiting indefinitely. No Qt dependency.
"""

import multiprocessing
import queue as queue_module
import threading
import time
from typing import Callable, Optional

from separateur_de_stems.core.errors import CancelledError, StemSeparatorError
from separateur_de_stems.core.platform import ensure_bundled_ffmpeg_on_path

_TERMINATE_TIMEOUT = 5.0
_POLL_SLICE = 0.05
_DRAIN_SLICE = 0.05
_DRAIN_BUDGET = 2.0


def _child_entry_point(
    worker_target, queue, input_path, stems, *args, progress_queue=None
):
    """Spawn-safe child entry: prepare the bundled ffmpeg, then run the worker.

    Spawn requires a picklable target, so the real worker is forwarded as an
    argument rather than closed over.
    """
    ensure_bundled_ffmpeg_on_path()
    worker_target(queue, input_path, stems, *args, progress_queue=progress_queue)


def _default_worker(queue, input_path, stems, engine_kwargs, progress_queue=None):
    """Real worker: runs a SeparationEngine inside the child process."""
    try:
        from separateur_de_stems.core.engine import SeparationEngine

        engine = SeparationEngine(**engine_kwargs)

        def progress_cb(percent, stage):
            if progress_queue is None:
                return
            try:
                progress_queue.put((percent, stage))
            except Exception:  # noqa: BLE001
                pass

        result = engine.run(input_path, stems, progress_cb=progress_cb)
        queue.put(("ok", dict(result)))
    except StemSeparatorError as error:
        queue.put(("error", str(error)))
    except Exception as error:  # noqa: BLE001
        queue.put(("error", f"unexpected: {error}"))
    finally:
        _close(queue)


def _close(queue) -> None:
    try:
        queue.close()
    except Exception:  # noqa: BLE001
        pass


class SubprocessSeparator:
    """Run a separation worker in a killable, cancellable child process."""

    def __init__(
        self,
        engine_kwargs: dict,
        worker_target=None,
        context=None,
        worker_args=(),
        progress_queue=None,
    ):
        self._engine_kwargs = dict(engine_kwargs)
        self._worker_target = worker_target or _default_worker
        self._worker_args = (
            tuple(worker_args) if worker_target is not None else (self._engine_kwargs,)
        )
        self._context = context or multiprocessing.get_context("spawn")
        self._progress_queue = progress_queue
        self._progress_queue_enabled = progress_queue is not None
        self._progress_queue_closed = False
        self._pending_progress = []
        self._queue = None
        self._process = None
        self._cancelled = threading.Event()
        self._lock = threading.Lock()

    def start(
        self,
        input_path: str,
        stems,
        progress_cb: Optional[Callable[[int, str], None]] = None,
    ) -> None:
        # Progress is reported through ``progress_queue``/``poll_progress``;
        # a callback cannot cross the process boundary, so reject it loudly
        # instead of silently ignoring it.
        if progress_cb is not None:
            raise ValueError(
                "progress_cb is not supported; use progress_queue instead"
            )
        with self._lock:
            if self._process is not None:
                raise RuntimeError("separation already running")
            if self._cancelled.is_set():
                return

            self._pending_progress = []
            self._ensure_progress_queue()
            self._queue = self._context.Queue()
            self._process = self._context.Process(
                target=_child_entry_point,
                args=(
                    self._worker_target,
                    self._queue,
                    input_path,
                    stems,
                    *self._worker_args,
                ),
                kwargs={"progress_queue": self._progress_queue},
            )
            self._process.start()

    def poll_progress(self) -> list:
        messages = self._pending_progress
        self._pending_progress = []
        progress_queue = self._progress_queue
        if progress_queue is not None:
            while True:
                try:
                    messages.append(progress_queue.get_nowait())
                except queue_module.Empty:
                    break
                except Exception:  # noqa: BLE001
                    break
        return messages

    def _ensure_progress_queue(self) -> None:
        if not self._progress_queue_enabled:
            return
        if self._progress_queue is None or self._progress_queue_closed:
            self._progress_queue = self._context.Queue()
            self._progress_queue_closed = False

    def poll(self, timeout: float = 0):
        with self._lock:
            if self._cancelled.is_set():
                self._terminate_locked()
                return ("cancelled", None)

            process = self._process
            if process is None:
                return None

            if timeout and timeout > 0:
                process.join(timeout)
            else:
                process.join(0)

            if process.is_alive():
                return None

            return self._drain_locked(process)

    def cancel(self) -> None:
        already = self._cancelled.is_set()
        self._cancelled.set()
        if already:
            return
        with self._lock:
            self._terminate_locked()

    def run(self, input_path: str, stems) -> dict:
        self.start(input_path, stems)
        while True:
            outcome = self.poll(timeout=_POLL_SLICE)
            if outcome is None:
                continue
            status, payload = outcome
            if status == "cancelled":
                raise CancelledError("Separation cancelled")
            if status == "error":
                raise StemSeparatorError(str(payload))
            return payload

    def _drain_locked(self, process):
        queue = self._queue
        status, payload = self._drain_result(queue)
        self._finish_locked(process, queue)
        if status is None:
            if self._cancelled.is_set():
                return ("cancelled", None)
            return ("error", "unexpected: worker exited without a result")
        return (status, payload)

    def _drain_result(self, queue):
        deadline = time.monotonic() + _DRAIN_BUDGET
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return (None, None)
            try:
                return queue.get(timeout=min(_DRAIN_SLICE, remaining))
            except queue_module.Empty:
                continue
            except Exception:  # noqa: BLE001
                return (None, None)

    def _finish_locked(self, process, queue) -> None:
        self._process = None
        self._queue = None
        if queue is not None:
            try:
                queue.close()
                queue.join_thread()
            except Exception:  # noqa: BLE001
                pass
        self._close_progress_queue()
        if process is not None and not process.is_alive():
            process.join(timeout=_TERMINATE_TIMEOUT)

    def _close_progress_queue(self) -> None:
        progress_queue = self._progress_queue
        if progress_queue is None:
            return
        self._pending_progress.extend(self._drain_progress_queue())
        try:
            progress_queue.close()
        except Exception:  # noqa: BLE001
            pass
        self._progress_queue_closed = True

    def _drain_progress_queue(self) -> list:
        progress_queue = self._progress_queue
        if progress_queue is None:
            return []
        messages = []
        while True:
            try:
                messages.append(progress_queue.get_nowait())
            except queue_module.Empty:
                break
            except Exception:  # noqa: BLE001
                break
        return messages

    def _terminate_locked(self) -> None:
        process = self._process
        queue = self._queue
        if process is not None:
            if process.is_alive():
                process.terminate()
                process.join(timeout=_TERMINATE_TIMEOUT)
            if process.is_alive():
                process.kill()
                process.join(timeout=_TERMINATE_TIMEOUT)
            if not process.is_alive():
                process.join()
        self._process = None
        self._queue = None
        if queue is not None:
            try:
                queue.cancel_join_thread()
                queue.close()
            except Exception:  # noqa: BLE001
                pass
        self._close_progress_queue()
