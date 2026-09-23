"""Tests for the QThread separation worker.

A fake ``SubprocessSeparator`` is injected through ``separator_factory`` so
no real separation, inference or network access ever happens. Qt runs in
offscreen mode and signals are awaited with ``qtbot.waitSignal``.
"""

import errno
import os
import threading
import time
from pathlib import Path

import pytest

from separateur_de_stems.core.errors import CancelledError, OutputError
from separateur_de_stems.ui import worker as worker_module
from separateur_de_stems.ui.run_context import RunContext
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


def _worker(factory, *, context=None, progress_queue=None):
    context = context or RunContext(
        "in.wav", "/out", "models", frozenset({"vocals"}), "/out"
    )
    return SeparationWorker(
        context,
        separator_factory=factory,
        finalize_outputs=lambda _context, outputs, **kwargs: list(outputs.values()),
        progress_queue=progress_queue,
    )


def test_worker_emits_completed(qtbot):
    factory = RetainedFactory(FakeSep)
    worker = _worker(factory)
    with qtbot.waitSignal(worker.completed, timeout=3000) as signal:
        worker.start()
    assert signal.args[0] == ["/tmp/v.wav"]


def test_worker_forwards_progress(qtbot):
    factory = RetainedFactory(FakeSep)
    worker = _worker(factory)
    with qtbot.waitSignal(worker.progress, timeout=3000) as signal:
        worker.start()
    assert signal.args == [50, "Separating vocals"]


def test_worker_emits_failed(qtbot):
    factory = RetainedFactory(lambda: FakeSep(outcome=("error", "boom")))
    worker = _worker(factory)
    with qtbot.waitSignal(worker.failed, timeout=3000) as signal:
        worker.start()
    assert "boom" in signal.args[0]


def test_worker_emits_cancelled_when_runner_cancelled(qtbot):
    class CancelAfterOnePollSep(FakeSep):
        def poll(self, timeout=0):
            self._polls += 1
            return ("cancelled", None)

    factory = RetainedFactory(CancelAfterOnePollSep)
    worker = _worker(factory)
    with qtbot.waitSignal(worker.cancelled, timeout=3000):
        worker.start()
    assert factory.last().started is True


def test_request_cancel_before_run_is_idempotent(qtbot):
    factory = RetainedFactory(FakeSep)
    worker = _worker(factory)
    worker.request_cancel()
    worker.request_cancel()
    with qtbot.waitSignal(worker.cancelled, timeout=3000):
        worker.start()
    assert factory.created == []


def test_request_cancel_during_run_cancels_separator(qtbot):
    factory = RetainedFactory(BlockingSep)
    worker = _worker(factory)

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
    context = RunContext(
        "in.wav", "/final/out", "/some/models", frozenset({"vocals"}), "/some/work"
    )
    worker = _worker(factory, context=context)
    with qtbot.waitSignal(worker.completed, timeout=3000):
        worker.start()
    kwargs = factory.factory_kwargs
    assert kwargs["engine_kwargs"]["model_dir"] == "/some/models"
    assert kwargs["engine_kwargs"]["output_dir"] == "/final/out"
    assert kwargs["engine_kwargs"]["_workspace"] == "/some/work"
    assert kwargs["progress_queue"] is not None


def test_unexpected_constructor_error_becomes_failed(qtbot):
    def exploding_factory(**kwargs):
        raise RuntimeError("no separator for you")

    worker = _worker(exploding_factory)
    with qtbot.waitSignal(worker.failed, timeout=3000) as signal:
        worker.start()
    assert "no separator for you" in signal.args[0]


def test_no_exception_escapes_run_when_start_raises(qtbot):
    class StartFailSep(FakeSep):
        def start(self, input_path, stems, progress_cb=None):
            raise ValueError("start exploded")

    factory = RetainedFactory(StartFailSep)
    worker = _worker(factory)
    with qtbot.waitSignal(worker.failed, timeout=3000) as signal:
        worker.start()
    assert "start exploded" in signal.args[0]


class TrackingQueue:
    """Stand-in for a multiprocessing queue recording close() calls."""

    def __init__(self):
        self.close_calls = 0

    def close(self):
        self.close_calls += 1


def test_worker_closes_its_own_progress_queue(qtbot):
    created = []

    def make_queue():
        queue = TrackingQueue()
        created.append(queue)
        return queue

    original = worker_module._create_progress_queue
    worker_module._create_progress_queue = make_queue
    try:
        factory = RetainedFactory(FakeSep)
        worker = _worker(factory)
        with qtbot.waitSignal(worker.completed, timeout=3000):
            worker.start()
    finally:
        worker_module._create_progress_queue = original
    assert len(created) == 1
    assert created[0].close_calls == 1


def test_worker_leaves_caller_progress_queue_open(qtbot):
    provided = TrackingQueue()
    factory = RetainedFactory(FakeSep)
    worker = _worker(factory, progress_queue=provided)
    with qtbot.waitSignal(worker.finished, timeout=3000):
        worker.start()
    assert provided.close_calls == 0


def test_runtime_error_becomes_failed(qtbot):
    class RuntimeFailSep(FakeSep):
        def start(self, input_path, stems, progress_cb=None):
            raise RuntimeError("runtime exploded")

    factory = RetainedFactory(RuntimeFailSep)
    worker = _worker(factory)
    with qtbot.waitSignal(worker.failed, timeout=3000) as signal:
        worker.start()
    assert "runtime exploded" in signal.args[0]


def test_system_exit_is_not_converted_to_failed(qtbot):
    class SystemExitSep(FakeSep):
        def start(self, input_path, stems, progress_cb=None):
            raise SystemExit(3)

    factory = RetainedFactory(SystemExitSep)
    worker = _worker(factory)
    failed = []
    worker.failed.connect(failed.append)

    escaped = []

    def invoke():
        try:
            worker.run()
        except SystemExit as error:
            escaped.append(error.code)

    runner = threading.Thread(target=invoke)
    runner.start()
    runner.join(timeout=3)

    assert runner.is_alive() is False
    assert escaped == [3]
    assert failed == []


def test_request_cancel_does_not_call_separator_from_caller_thread(qtbot):
    factory = RetainedFactory(BlockingSep)
    worker = _worker(factory)
    requester_threads = []
    cancel_threads = []

    def record_cancel():
        cancel_threads.append(threading.get_ident())
        factory.last().cancelled = True

    def request_when_started():
        assert _wait_for(lambda: factory.last() is not None and factory.last().started)
        factory.last().cancel = record_cancel
        requester_threads.append(threading.get_ident())
        worker.request_cancel()

    timer = threading.Thread(target=request_when_started)
    timer.start()
    try:
        with qtbot.waitSignal(worker.cancelled, timeout=3000):
            worker.start()
    finally:
        timer.join(timeout=3)

    assert cancel_threads
    assert cancel_threads != requester_threads


def _run_context(tmp_path, stems=frozenset({"vocals", "instrumental"})):
    workspace = tmp_path / "out" / ".run"
    workspace.mkdir(parents=True)
    input_path = tmp_path / "song.wav"
    input_path.write_bytes(b"input")
    return RunContext(
        str(input_path),
        str(tmp_path / "out"),
        str(tmp_path / "models"),
        stems,
        str(workspace),
    )


def _writing_exporter(src, dest):
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    Path(dest).write_bytes(Path(src).read_bytes())
    return dest


def _cancellable_writing_exporter(src, dest, **kwargs):
    return _writing_exporter(src, dest)


def test_partial_result_publishes_no_deliverables(tmp_path):
    context = _run_context(tmp_path)
    raw = Path(context.workspace) / "vocals.wav"
    raw.write_bytes(b"raw")

    with pytest.raises(OutputError, match="Missing outputs"):
        worker_module._finalize_outputs(
            context,
            {"vocals": str(raw)},
            wav_exporter=_writing_exporter,
            mp3_exporter=_cancellable_writing_exporter,
        )

    assert list(Path(context.output_dir).glob("song/*")) == []


def test_export_failure_publishes_no_partial_deliverables(tmp_path):
    context = _run_context(tmp_path)
    outputs = {}
    for stem in context.stems:
        raw = Path(context.workspace) / f"{stem}.wav"
        raw.write_bytes(stem.encode())
        outputs[stem] = str(raw)

    calls = 0

    def fail_second_mp3(src, dest, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("encoding failed")
        return _writing_exporter(src, dest)

    with pytest.raises(RuntimeError, match="encoding failed"):
        worker_module._finalize_outputs(
            context,
            outputs,
            wav_exporter=_writing_exporter,
            mp3_exporter=fail_second_mp3,
        )

    assert (Path(context.output_dir) / "song").exists() is False


def test_existing_song_directory_is_preserved_without_overwrite(tmp_path):
    context = _run_context(tmp_path, frozenset({"vocals"}))
    final_dir = Path(context.output_dir) / "song"
    final_dir.mkdir()
    existing = final_dir / "song_vocals.wav"
    existing.write_bytes(b"keep")
    raw = Path(context.workspace) / "vocals.wav"
    raw.write_bytes(b"new")

    with pytest.raises(FileExistsError):
        worker_module._finalize_outputs(
            context,
            {"vocals": str(raw)},
            wav_exporter=_writing_exporter,
            mp3_exporter=_cancellable_writing_exporter,
        )

    assert existing.read_bytes() == b"keep"


@pytest.mark.parametrize("destination_kind", ["file", "empty_directory"])
def test_existing_destination_path_is_never_replaced(tmp_path, destination_kind):
    context = _run_context(tmp_path, frozenset({"vocals"}))
    destination = Path(context.output_dir) / "song"
    if destination_kind == "file":
        destination.write_bytes(b"keep")
    else:
        destination.mkdir()
    raw = Path(context.workspace) / "vocals.wav"
    raw.write_bytes(b"new")

    with pytest.raises(FileExistsError):
        worker_module._finalize_outputs(
            context,
            {"vocals": str(raw)},
            wav_exporter=_writing_exporter,
            mp3_exporter=_cancellable_writing_exporter,
        )

    if destination_kind == "file":
        assert destination.read_bytes() == b"keep"
    else:
        assert list(destination.iterdir()) == []


def test_finalization_runs_in_worker_thread(qtbot, tmp_path):
    context = _run_context(tmp_path, frozenset({"vocals"}))
    factory = RetainedFactory(FakeSep)
    thread_ids = []

    def finalize(run_context, outputs, **kwargs):
        thread_ids.append(threading.get_ident())
        return [str(Path(run_context.output_dir) / "song" / "song_vocals.wav")]

    worker = SeparationWorker(
        context, separator_factory=factory, finalize_outputs=finalize
    )
    gui_thread = threading.get_ident()

    with qtbot.waitSignal(worker.completed, timeout=3000):
        worker.start()

    assert thread_ids
    assert thread_ids != [gui_thread]


def test_final_directory_appears_only_after_complete_batch(tmp_path):
    context = _run_context(tmp_path, frozenset({"vocals"}))
    raw = Path(context.workspace) / "vocals.wav"
    raw.write_bytes(b"new")
    final_dir = Path(context.output_dir) / "song"

    def observing_mp3(src, dest, **kwargs):
        assert final_dir.exists() is False
        return _writing_exporter(src, dest)

    published = worker_module._finalize_outputs(
        context,
        {"vocals": str(raw)},
        wav_exporter=_writing_exporter,
        mp3_exporter=observing_mp3,
    )

    assert final_dir.is_dir()
    assert {path.name for path in final_dir.iterdir()} == {
        "song_vocals.wav",
        "song_vocals.mp3",
    }
    assert set(published) == {str(path) for path in final_dir.iterdir()}


@pytest.mark.parametrize("conflict_kind", ["file", "directory"])
def test_atomic_publish_preserves_destination_winning_race(
    tmp_path, monkeypatch, conflict_kind
):
    context = _run_context(tmp_path, frozenset({"vocals"}))
    raw = Path(context.workspace) / "vocals.wav"
    raw.write_bytes(b"new")
    final_dir = Path(context.output_dir) / "song"

    def racing_rename(source, destination):
        if conflict_kind == "file":
            Path(destination).write_bytes(b"preexisting")
        else:
            Path(destination).mkdir()
        raise FileExistsError(destination)

    monkeypatch.setattr(worker_module, "_rename_no_replace", racing_rename)

    with pytest.raises(FileExistsError):
        worker_module._finalize_outputs(
            context,
            {"vocals": str(raw)},
            wav_exporter=_writing_exporter,
            mp3_exporter=_cancellable_writing_exporter,
        )

    if conflict_kind == "file":
        assert final_dir.read_bytes() == b"preexisting"
    else:
        assert list(final_dir.iterdir()) == []


def test_cross_device_publish_fails_without_visible_destination(tmp_path, monkeypatch):
    context = _run_context(tmp_path, frozenset({"vocals"}))
    raw = Path(context.workspace) / "vocals.wav"
    raw.write_bytes(b"new")

    def cross_device_rename(source, destination):
        raise OSError(errno.EXDEV, "cross-device")

    monkeypatch.setattr(worker_module, "_rename_no_replace", cross_device_rename)

    with pytest.raises(OSError, match="cross-device"):
        worker_module._finalize_outputs(
            context,
            {"vocals": str(raw)},
            wav_exporter=_writing_exporter,
            mp3_exporter=_cancellable_writing_exporter,
        )

    assert (Path(context.output_dir) / "song").exists() is False


def test_cancel_during_slow_export_emits_only_cancelled_and_publishes_nothing(
    qtbot, tmp_path
):
    context = _run_context(tmp_path, frozenset({"vocals"}))
    raw = Path(context.workspace) / "vocals.wav"
    raw.write_bytes(b"raw")
    factory = RetainedFactory(
        lambda: FakeSep(outcome=("ok", {"vocals": str(raw)}), terminal_after_polls=1)
    )
    entered = threading.Event()

    def slow_mp3(src, dest, cancel_requested=None):
        entered.set()
        while not cancel_requested():
            time.sleep(0.01)
        raise CancelledError("cancelled")

    def finalize(run_context, outputs, cancel_requested=None):
        return worker_module._finalize_outputs(
            run_context,
            outputs,
            wav_exporter=_writing_exporter,
            mp3_exporter=slow_mp3,
            cancel_requested=cancel_requested,
        )

    worker = SeparationWorker(
        context, separator_factory=factory, finalize_outputs=finalize
    )
    completed = []
    failed = []
    worker.completed.connect(completed.append)
    worker.failed.connect(failed.append)
    worker.start()
    assert entered.wait(timeout=2)

    started = time.monotonic()
    with qtbot.waitSignal(worker.cancelled, timeout=1000):
        worker.request_cancel()

    assert time.monotonic() - started < 0.5
    assert completed == []
    assert failed == []
    assert (Path(context.output_dir) / "song").exists() is False
