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


def sleeping_worker(queue, input_path, stems, sleep_seconds):
    """Simulates a long separation that never finishes on its own."""
    try:
        time.sleep(sleep_seconds)
        queue.put(("ok", {"vocals": "vocals.wav"}))
    finally:
        queue.close()


def echo_worker(queue, input_path, stems, payload):
    """Returns a serializable result dict immediately."""
    try:
        queue.put(("ok", dict(payload)))
    finally:
        queue.close()


def failing_worker(queue, input_path, stems, message):
    """Raises a project error inside the subprocess."""
    try:
        raise OutputError(message)
    except OutputError as error:
        queue.put(("error", str(error)))
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


def _wait_status(runner, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        outcome = runner.poll(timeout=0.1)
        if outcome is not None:
            return outcome
    raise AssertionError("runner did not reach a terminal status in time")
