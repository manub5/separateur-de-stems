"""Cancellable subprocess runner for stem separation.

Runs a separation worker in a killable child process so the UI thread can
request cancellation without waiting indefinitely. No Qt dependency.
"""

import multiprocessing
import threading
from typing import Callable, Optional

from separateur_de_stems.core.errors import CancelledError, StemSeparatorError

_TERMINATE_TIMEOUT = 5.0
_POLL_SLICE = 0.05
_DRAIN_TIMEOUT = 1.0


def _default_worker(queue, input_path, stems, engine_kwargs):
    """Real worker: runs a SeparationEngine inside the child process."""
    try:
        from separateur_de_stems.core.engine import SeparationEngine

        engine = SeparationEngine(**engine_kwargs)
        result = engine.run(input_path, stems)
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
    ):
        self._engine_kwargs = dict(engine_kwargs)
        self._worker_target = worker_target or _default_worker
        self._worker_args = (
            tuple(worker_args) if worker_target is not None else (self._engine_kwargs,)
        )
        self._context = context or multiprocessing.get_context("spawn")
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
        del progress_cb
        with self._lock:
            if self._cancelled.is_set():
                return

            self._queue = self._context.Queue()
            self._process = self._context.Process(
                target=self._worker_target,
                args=(self._queue, input_path, stems, *self._worker_args),
            )
            self._process.start()

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
        try:
            status, payload = queue.get(timeout=_DRAIN_TIMEOUT)
        except Exception:  # noqa: BLE001
            self._finish_locked(process, queue)
            if self._cancelled.is_set():
                return ("cancelled", None)
            return ("error", "unexpected: worker exited without a result")
        self._finish_locked(process, queue)
        return (status, payload)

    def _finish_locked(self, process, queue) -> None:
        self._process = None
        self._queue = None
        if queue is not None:
            try:
                queue.close()
                queue.join_thread()
            except Exception:  # noqa: BLE001
                pass
        if process is not None and not process.is_alive():
            process.join(timeout=_TERMINATE_TIMEOUT)

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
