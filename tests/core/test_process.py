"""Tests for cancellable subprocess separation runner (no ML, no network)."""

import multiprocessing
import os
import sys
import threading
import time

import pytest

from separateur_de_stems.core.errors import (
    CancelledError,
    OutputError,
    StemSeparatorError,
)
from separateur_de_stems.core.process import SubprocessSeparator
from separateur_de_stems.core.platform import ensure_bundled_ffmpeg_on_path


def sleeping_worker(queue, input_path, stems, sleep_seconds, progress_queue=None):
    """Simulates a long separation that never finishes on its own."""
    try:
        time.sleep(sleep_seconds)
        queue.put(("ok", {"vocals": "vocals.wav"}))
    finally:
        queue.close()


def echo_worker(queue, input_path, stems, payload, progress_queue=None):
    """Returns a serializable result dict immediately."""
    try:
        queue.put(("ok", dict(payload)))
    finally:
        queue.close()


def env_echo_worker(queue, input_path, stems, progress_queue=None):
    """Returns the PATH and ffmpeg resolution seen inside the child process."""
    from pydub.utils import which

    try:
        queue.put(
            (
                "ok",
                {
                    "path": os.environ.get("PATH", ""),
                    "which": which("ffmpeg"),
                },
            )
        )
    finally:
        queue.close()


def failing_worker(queue, input_path, stems, message, progress_queue=None):
    """Raises a project error inside the subprocess."""
    try:
        raise OutputError(message)
    except OutputError as error:
        queue.put(("error", str(error)))
    finally:
        queue.close()


def _sleeping_progress_worker(queue, input_path, stems, sleep_seconds, progress_queue=None):
    """Sleeps, then reports a result; drains progress messages meanwhile."""
    try:
        deadline = time.monotonic() + sleep_seconds
        while time.monotonic() < deadline:
            time.sleep(0.05)
        queue.put(("ok", {"vocals": "vocals.wav"}))
    finally:
        queue.close()


def _progress_emitting_worker(queue, input_path, stems, progress_queue=None):
    """Emits progress messages then a terminal result."""
    try:
        if progress_queue is not None:
            progress_queue.put((10, "Loading model"))
            progress_queue.put((50, "Separating"))
        queue.put(("ok", {"vocals": "vocals.wav"}))
    finally:
        queue.close()


def setup_function():
    _drain_children()


def teardown_function():
    _drain_children()


def _drain_children():
    for child in multiprocessing.active_children():
        child.terminate()
        child.join(timeout=5)


def test_poll_returns_none_while_running_then_status(tmp_path):
    runner = SubprocessSeparator(
        engine_kwargs={},
        worker_target=sleeping_worker,
        worker_args=(1.5,),
    )
    runner.start(str(tmp_path / "in.wav"), {"vocals"})

    assert runner.poll(timeout=0) is None

    status, result = _wait_status(runner, timeout=10)
    assert status == "ok"
    assert result == {"vocals": "vocals.wav"}
    assert not any(p.is_alive() for p in multiprocessing.active_children())


def test_worker_result_is_returned(tmp_path):
    runner = SubprocessSeparator(
        engine_kwargs={},
        worker_target=echo_worker,
        worker_args=({"vocals": "vocals.wav"},),
    )
    runner.start(str(tmp_path / "in.wav"), {"vocals"})

    status, result = _wait_status(runner, timeout=10)
    assert status == "ok"
    assert result == {"vocals": "vocals.wav"}


def test_worker_project_error_is_reported(tmp_path):
    runner = SubprocessSeparator(
        engine_kwargs={}, worker_target=failing_worker, worker_args=("boom",)
    )
    runner.start(str(tmp_path / "in.wav"), {"vocals"})

    status, result = _wait_status(runner, timeout=10)
    assert status == "error"
    assert "boom" in result


def test_run_raises_project_error_with_message(tmp_path):
    runner = SubprocessSeparator(
        engine_kwargs={}, worker_target=failing_worker, worker_args=("boom",)
    )

    with pytest.raises(StemSeparatorError) as excinfo:
        runner.run(str(tmp_path / "in.wav"), {"vocals"})

    assert "boom" in str(excinfo.value)


def test_start_rejects_progress_cb(tmp_path):
    """``progress_cb`` is not part of the contract: progress uses the queue."""
    runner = SubprocessSeparator(
        engine_kwargs={},
        worker_target=echo_worker,
        worker_args=({"vocals": "out.wav"},),
    )

    with pytest.raises(ValueError, match="progress_cb"):
        runner.start(str(tmp_path / "in.wav"), {"vocals"}, progress_cb=lambda p, m: None)


def test_run_returns_result_dict(tmp_path):
    runner = SubprocessSeparator(
        engine_kwargs={},
        worker_target=echo_worker,
        worker_args=({"vocals": "out.wav"},),
    )

    result = runner.run(str(tmp_path / "in.wav"), {"vocals"})

    assert result == {"vocals": "out.wav"}


def test_cancel_during_execution_marks_cancelled(tmp_path):
    runner = SubprocessSeparator(
        engine_kwargs={}, worker_target=sleeping_worker, worker_args=(30,)
    )
    runner.start(str(tmp_path / "in.wav"), {"vocals"})

    canceller = threading.Thread(target=runner.cancel)
    canceller.start()
    canceller.join(timeout=10)

    status, result = _wait_status(runner, timeout=10)
    assert status == "cancelled"
    assert result is None
    assert not any(p.is_alive() for p in multiprocessing.active_children())


def test_run_raises_cancelled_when_cancelled_during_execution(tmp_path):
    runner = SubprocessSeparator(
        engine_kwargs={}, worker_target=sleeping_worker, worker_args=(30,)
    )

    canceller = threading.Timer(0.3, runner.cancel)
    canceller.start()
    try:
        with pytest.raises(CancelledError):
            runner.run(str(tmp_path / "in.wav"), {"vocals"})
    finally:
        canceller.cancel()

    assert not any(p.is_alive() for p in multiprocessing.active_children())


def test_cancel_before_start_gives_immediate_cancellation(tmp_path):
    runner = SubprocessSeparator(
        engine_kwargs={},
        worker_target=echo_worker,
        worker_args=({"vocals": "out.wav"},),
    )
    runner.cancel()

    runner.start(str(tmp_path / "in.wav"), {"vocals"})

    status, result = _wait_status(runner, timeout=10)
    assert status == "cancelled"
    assert result is None


def test_cancel_is_idempotent(tmp_path):
    runner = SubprocessSeparator(
        engine_kwargs={}, worker_target=sleeping_worker, worker_args=(30,)
    )
    runner.start(str(tmp_path / "in.wav"), {"vocals"})

    runner.cancel()
    runner.cancel()

    status, _ = _wait_status(runner, timeout=10)
    assert status == "cancelled"
    assert not any(p.is_alive() for p in multiprocessing.active_children())


def test_start_twice_raises_runtime_error(tmp_path):
    runner = SubprocessSeparator(
        engine_kwargs={},
        worker_target=_sleeping_progress_worker,
        worker_args=(30,),
    )
    runner.start(str(tmp_path / "in.wav"), {"vocals"})

    children_before = {p.pid for p in multiprocessing.active_children()}
    try:
        with pytest.raises(RuntimeError, match="separation already running"):
            runner.start(str(tmp_path / "in.wav"), {"vocals"})
        children_after = {p.pid for p in multiprocessing.active_children()}
        assert children_after == children_before
    finally:
        runner.cancel()


def test_failed_process_start_resets_state_closes_queue_and_allows_retry(tmp_path):
    class Queue:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

        def join_thread(self):
            pass

    class Process:
        attempts = 0

        def start(self):
            Process.attempts += 1
            if Process.attempts == 1:
                raise OSError("spawn boom")

        def join(self, timeout=0):
            pass

        def is_alive(self):
            return False

    class Context:
        def __init__(self):
            self.queues = []

        def Queue(self):
            queue = Queue()
            self.queues.append(queue)
            return queue

        def Process(self, **kwargs):
            return Process()

    context = Context()
    runner = SubprocessSeparator(engine_kwargs={}, context=context)

    with pytest.raises(OSError, match="spawn boom"):
        runner.start(str(tmp_path / "in.wav"), {"vocals"})

    assert context.queues[0].closed is True
    runner.start(str(tmp_path / "in.wav"), {"vocals"})


def test_instance_can_run_twice_with_progress_queue(tmp_path):
    context = multiprocessing.get_context("spawn")
    progress_queue = context.Queue()
    runner = SubprocessSeparator(
        engine_kwargs={},
        worker_target=_progress_emitting_worker,
        worker_args=(),
        progress_queue=progress_queue,
    )

    first = runner.run(str(tmp_path / "in.wav"), {"vocals"})
    first_progress = _wait_progress(runner, timeout=10)
    second = runner.run(str(tmp_path / "in.wav"), {"vocals"})
    second_progress = _wait_progress(runner, timeout=10)

    assert first == {"vocals": "vocals.wav"}
    assert second == {"vocals": "vocals.wav"}
    assert (10, "Loading model") in first_progress
    assert (10, "Loading model") in second_progress


def test_poll_progress_collects_worker_messages(tmp_path):
    context = multiprocessing.get_context("spawn")
    progress_queue = context.Queue()
    runner = SubprocessSeparator(
        engine_kwargs={},
        worker_target=_progress_emitting_worker,
        worker_args=(),
        progress_queue=progress_queue,
    )
    runner.start(str(tmp_path / "in.wav"), {"vocals"})

    messages, outcome = _collect_progress(runner, timeout=10)
    status, result = outcome
    assert status == "ok"
    assert result == {"vocals": "vocals.wav"}
    assert (10, "Loading model") in messages
    assert (50, "Separating") in messages


def test_run_without_progress_queue_still_returns_result(tmp_path):
    runner = SubprocessSeparator(
        engine_kwargs={},
        worker_target=echo_worker,
        worker_args=({"vocals": "out.wav"},),
    )

    result = runner.run(str(tmp_path / "in.wav"), {"vocals"})

    assert result == {"vocals": "out.wav"}


def _wait_progress(runner, timeout):
    deadline = time.monotonic() + timeout
    messages = []
    while time.monotonic() < deadline:
        messages.extend(runner.poll_progress())
        if messages:
            return messages
        time.sleep(0.05)
    return messages


def _collect_progress(runner, timeout):
    deadline = time.monotonic() + timeout
    messages = []
    while time.monotonic() < deadline:
        messages.extend(runner.poll_progress())
        outcome = runner.poll(timeout=0)
        if outcome is not None:
            messages.extend(runner.poll_progress())
            return messages, outcome
        time.sleep(0.05)
    raise AssertionError("runner did not reach a terminal status in time")


def test_spawn_child_sees_bundled_ffmpeg_on_path(monkeypatch, tmp_path):
    """A spawned child inherits the PATH we prepend to ``os.environ``.

    This mirrors the frozen app: ``ensure_bundled_ffmpeg_on_path`` runs first,
    then ``SubprocessSeparator`` spawns the child, which must see the bundled
    ffmpeg directory on its PATH. ``sys._MEIPASS`` is a per-process attribute
    (not inherited by ``spawn``), so the child relies on the parent's PATH and
    on its own runtime-hook/entry-point re-initialisation in a real bundle.
    """
    bundle = tmp_path / "bundle"
    ffmpeg_dir = bundle / "ffmpeg"
    ffmpeg_dir.mkdir(parents=True)
    binary = ffmpeg_dir / "ffmpeg"
    binary.write_bytes(b"#!/bin/sh\n")
    binary.chmod(0o755)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)

    original_path = os.environ.get("PATH")
    try:
        assert ensure_bundled_ffmpeg_on_path() == str(binary)

        runner = SubprocessSeparator(
            engine_kwargs={}, worker_target=env_echo_worker
        )

        result = runner.run(str(tmp_path / "in.wav"), {"vocals"})

        assert result["path"].split(os.pathsep)[0] == str(ffmpeg_dir)
        assert result["which"] == str(binary)
    finally:
        if original_path is None:
            os.environ.pop("PATH", None)
        else:
            os.environ["PATH"] = original_path


def _wait_status(runner, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        outcome = runner.poll(timeout=0.1)
        if outcome is not None:
            return outcome
    raise AssertionError("runner did not reach a terminal status in time")
