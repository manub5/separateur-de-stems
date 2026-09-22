"""Tests for the QThread separation worker.

A fake ``SubprocessSeparator`` is injected through ``separator_factory`` so
no real separation, inference or network access ever happens. Qt runs in
offscreen mode and signals are awaited with ``qtbot.waitSignal``.
"""

import threading
import time

from separateur_de_stems.ui.worker import SeparationWorker


def _wait_for(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


class RetainedFactory:
    """Callable factory that keeps the created separator for inspection."""

    def __init__(self, separator_class):
        self._separator_class = separator_class
        self.created = []

    def __call__(self, **kwargs):
        self.factory_kwargs = dict(kwargs)
        separator = self._separator_class()
        self.created.append(separator)
        return separator

    def last(self):
        return self.created[-1] if self.created else None


class FakeSep:
    """Minimal stand-in for ``SubprocessSeparator`` driven by tests."""

    def __init__(self, outcome=None, terminal_after_polls=2):
        self.started = False
        self.start_args = None
        self.cancelled = False
        self.cancel_calls = 0
        self.progress_messages = [(50, "Separating vocals")]
        if outcome is None:
            outcome = ("ok", {"vocals": "/tmp/v.wav"})
        self._outcome = outcome
        self._terminal_after_polls = terminal_after_polls
        self._polls = 0
        self.on_poll = None

    def start(self, input_path, stems, progress_cb=None):
        self.started = True
        self.start_args = (input_path, stems, progress_cb)

    def poll(self, timeout=0):
        self._polls += 1
        if self.on_poll is not None:
            self.on_poll(self._polls)
        if self._polls < self._terminal_after_polls:
            return None
        if self._outcome[0] == "cancelled":
            return ("cancelled", None)
        return self._outcome

    def cancel(self):
        self.cancelled = True
        self.cancel_calls += 1

    def poll_progress(self):
        messages = self.progress_messages
        self.progress_messages = []
        return messages


class BlockingSep(FakeSep):
    """Runs until cancelled, then reports a terminal ``cancelled`` status."""

    def __init__(self, terminal_after_polls=10**9):
        super().__init__(terminal_after_polls=terminal_after_polls)

    def poll(self, timeout=0):
        self._polls += 1
        if self.on_poll is not None:
            self.on_poll(self._polls)
        if self.cancelled:
            return ("cancelled", None)
        return None


def test_worker_emits_finished(qtbot):
    factory = RetainedFactory(FakeSep)
    worker = SeparationWorker(
        "in.wav", {"vocals"}, "/out", "models", separator_factory=factory
    )
    with qtbot.waitSignal(worker.finished, timeout=3000) as signal:
        worker.start()
    assert signal.args[0] == {"vocals": "/tmp/v.wav"}


def test_worker_forwards_progress(qtbot):
    factory = RetainedFactory(FakeSep)
    worker = SeparationWorker(
        "in.wav", {"vocals"}, "/out", "models", separator_factory=factory
    )
    with qtbot.waitSignal(worker.progress, timeout=3000) as signal:
        worker.start()
    assert signal.args == [50, "Separating vocals"]


def test_worker_emits_failed(qtbot):
    factory = RetainedFactory(lambda: FakeSep(outcome=("error", "boom")))
    worker = SeparationWorker(
        "in.wav", {"vocals"}, "/out", "models", separator_factory=factory
    )
    with qtbot.waitSignal(worker.failed, timeout=3000) as signal:
        worker.start()
    assert "boom" in signal.args[0]


def test_worker_emits_cancelled_when_runner_cancelled(qtbot):
    class CancelAfterOnePollSep(FakeSep):
        def poll(self, timeout=0):
            self._polls += 1
            return ("cancelled", None)

    factory = RetainedFactory(CancelAfterOnePollSep)
    worker = SeparationWorker(
        "in.wav", {"vocals"}, "/out", "models", separator_factory=factory
    )
    with qtbot.waitSignal(worker.cancelled, timeout=3000):
        worker.start()
    assert factory.last().started is True


def test_request_cancel_before_run_is_idempotent(qtbot):
    factory = RetainedFactory(FakeSep)
    worker = SeparationWorker(
        "in.wav", {"vocals"}, "/out", "models", separator_factory=factory
    )
    worker.request_cancel()
    worker.request_cancel()
    with qtbot.waitSignal(worker.cancelled, timeout=3000):
        worker.start()
    assert factory.created == []


def test_request_cancel_during_run_cancels_separator(qtbot):
    factory = RetainedFactory(BlockingSep)
    worker = SeparationWorker(
        "in.wav", {"vocals"}, "/out", "models", separator_factory=factory
    )

    def cancel_when_started():
        if not _wait_for(lambda: factory.last() is not None and factory.last().started):
            return
        worker.request_cancel()

    canceller = threading.Thread(target=cancel_when_started)
    canceller.start()
    try:
        with qtbot.waitSignal(worker.cancelled, timeout=3000):
            worker.start()
    finally:
        canceller.join(timeout=3)
    assert factory.last().cancelled is True


def test_factory_receives_model_and_output_dir(qtbot):
    factory = RetainedFactory(FakeSep)
    worker = SeparationWorker(
        "in.wav", {"vocals"}, "/some/out", "/some/models", separator_factory=factory
    )
    with qtbot.waitSignal(worker.finished, timeout=3000):
        worker.start()
    kwargs = factory.factory_kwargs
    assert kwargs["engine_kwargs"]["model_dir"] == "/some/models"
    assert kwargs["engine_kwargs"]["output_dir"] == "/some/out"
    assert kwargs["progress_queue"] is not None


def test_unexpected_constructor_error_becomes_failed(qtbot):
    def exploding_factory(**kwargs):
        raise RuntimeError("no separator for you")

    worker = SeparationWorker(
        "in.wav", {"vocals"}, "/out", "models", separator_factory=exploding_factory
    )
    with qtbot.waitSignal(worker.failed, timeout=3000) as signal:
        worker.start()
    assert "no separator for you" in signal.args[0]


def test_no_exception_escapes_run_when_start_raises(qtbot):
    class StartFailSep(FakeSep):
        def start(self, input_path, stems, progress_cb=None):
            raise ValueError("start exploded")

    factory = RetainedFactory(StartFailSep)
    worker = SeparationWorker(
        "in.wav", {"vocals"}, "/out", "models", separator_factory=factory
    )
    with qtbot.waitSignal(worker.failed, timeout=3000) as signal:
        worker.start()
    assert "start exploded" in signal.args[0]
