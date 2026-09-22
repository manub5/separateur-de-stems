# Task 1 Report — Safe UI Run Lifecycle

## Status

Implemented the Task 1 lifecycle hardening in the designated worktree.

## Changes

- Added frozen `RunContext` with captured input, output, model, stem, and private workspace values.
- Validated readable regular inputs, writable or creatable outputs, and readable model directories before launch.
- Honoured the trimmed configured model directory with the bundled/default path as fallback.
- Routed separator intermediates to a private workspace and removed only that workspace at native thread completion.
- Renamed the worker's successful terminal signal to `completed`, preserving native `QThread.finished` for lifecycle cleanup.
- Made cancellation event-only in the caller; the worker thread performs separator cancellation while polling.
- Kept the worker reference and all mutable run controls locked until native thread completion.
- Deferred active-window close until cancellation and native thread completion finish.
- Rejected empty, incomplete, missing-file, and absent-terminal results as failures.
- Made export naming and destination derive exclusively from the captured `RunContext`.

## TDD Evidence

The initial test run failed during collection because `RunContext` did not exist. After adding only the immutable type, the lifecycle suite failed in nine expected places: missing `completed`, unlocked controls, absent captured context, immediate close, and premature relaunch. A later focused red test proved that native completion without a terminal result was not reported as failure. The implementation was then added incrementally until the prescribed UI suite passed.

## Verification

Command:

```text
QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest tests/ui -q
```

Result: `131 passed in 2.65s` on the final pre-commit run.

## Review Notes

- Cleanup is idempotent through `shutil.rmtree(..., ignore_errors=True)` and never scans or deletes user output files.
- Invalid paths can create the requested output directory during preflight validation; this is the intended validation side effect.
- WAV/MP3 export now runs in `SeparationWorker`, so conversion cannot block the GUI event loop. Task 2 can still centralize this temporary integration in the pipeline.
- macOS-specific thread and close behaviour cannot be exercised on Linux; Qt offscreen tests cover the platform-independent lifecycle.

## Review Fix Commit

The review findings were addressed with these changes:

- `SeparationWorker` now receives only `RunContext`, performs export in its own thread, and emits success only after publication.
- All WAV/MP3 files are built and validated under the private workspace. The complete song directory is renamed into place only after every requested deliverable exists.
- Existing destination song directories cause a failure and remain untouched; no implicit overwrite occurs.
- Missing stems and export failures leave no final deliverables.
- Missing-input validation is exercised with otherwise valid output and model paths and asserts the visible failure.
- Worker construction and `start()` failures now clean the workspace, clear retained state, unlock controls, and report the error.

TDD red runs reproduced missing atomic finalization, GUI-thread export, invalid factory shape, and uncaught launch exceptions. The focused red run reported six expected failures before implementation. The first full green UI run after the correction was:

```text
QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest tests/ui -q
133 passed in 2.67s
```

Final pre-commit verification:

```text
QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest tests/ui -q
133 passed in 2.46s
git diff --check
exit 0
```

## Review Fix Round 2

- Publication now creates the destination directory atomically and publishes each staged file with `os.link`, which cannot replace an existing file.
- A destination file or directory that wins a race is preserved. Files linked by the current run are tracked and rolled back if any later link, cancellation, or cross-device operation fails.
- Export cancellation is checked before and after every WAV/MP3 conversion and before every publication operation.
- Cancellable MP3 export uses `subprocess.Popen` polling, terminates ffmpeg on cancellation, escalates to `kill()` after a timeout, and removes its partial output.
- `CancelledError` follows only the worker's `cancelled` terminal path; it does not also emit failure or completion.
- Active close during a controlled slow export requests cancellation, waits for native thread completion, removes the workspace, and publishes nothing.

TDD red verification reproduced all five initially missing behaviours: cancellable MP3, file and directory publication races, cross-device rollback, and cancellation during slow export. Focused green verification:

```text
QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest \
  tests/core/test_export.py::test_to_mp3_320_terminates_process_when_cancelled \
  tests/ui/test_worker.py::test_publication_does_not_replace_destination_created_during_publish \
  tests/ui/test_worker.py::test_publication_failure_rolls_back_only_files_linked_by_run \
  tests/ui/test_worker.py::test_cancel_during_slow_export_emits_only_cancelled_and_publishes_nothing -q
5 passed in 0.10s
```

Pre-commit suite runs before the round 2 commit:

```text
QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest tests/ui -q
140 passed in 2.61s

../../.venv/bin/python -m pytest tests/core/test_export.py -q
18 passed in 0.24s
```
