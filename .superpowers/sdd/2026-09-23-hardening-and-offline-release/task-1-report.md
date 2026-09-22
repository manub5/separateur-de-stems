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
- GUI-side WAV/MP3 export remains synchronous legacy behaviour. Moving export into the background process is outside this task, but remains a responsiveness concern for a later task.
- macOS-specific thread and close behaviour cannot be exercised on Linux; Qt offscreen tests cover the platform-independent lifecycle.
