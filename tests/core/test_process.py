"""Tests for cancellable subprocess separation runner (no ML, no network)."""

import multiprocessing
import threading
import time

import pytest

from separateur_de_stems.core.errors import (
    CancelledError,
    OutputError,
    StemSeparatorError,
)
from separateur_de_stems.core.process import SubprocessSeparator


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


def _wait_status(runner, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        outcome = runner.poll(timeout=0.1)
        if outcome is not None:
            return outcome
    raise AssertionError("runner did not reach a terminal status in time")
