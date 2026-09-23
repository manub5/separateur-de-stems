# Task 2 Report — Background Export And Robust Engine

## Status

Implemented Task 2 in the designated hardening worktree.

## Changes

- Added `core.pipeline.run_pipeline()` as the single boundary for separation,
  complete-result validation, WAV/MP3 export, atomic publication, progress, and
  private-workspace cleanup.
- Routed both the CLI and the subprocess-backed UI worker through the pipeline.
- Preserved Task 1's immutable `RunContext`, non-blocking cancellation, worker
  signals, private workspace, and atomic no-replace publication behavior.
- Confined every model output, including ignored auxiliary outputs, to the run
  workspace. External output paths are rejected and never removed.
- Made failure and cancellation publish nothing and clean only a validated
  private run workspace.
- Converted catalogue, separator construction, and model loading failures to
  contextual `ModelUnavailableError` instances.
- Made `SubprocessSeparator.start()` transactional: failed queue/process/start
  setup closes owned resources, clears state, and permits retry.
- Reworked WAV 24-bit conversion to fixed 65,536-frame blocks while preserving
  cancellable argument-list MP3 encoding.
- Reserved progress 0–80 for separation and 81–99 for export, with 100 emitted
  only after publication; the UI translates structured export/finalization
  stages.
- Replaced CLI cleanup/export duplication with direct pipeline consumption.

## TDD Evidence

The initial focused red runs demonstrated the missing pipeline module, raw
catalogue/factory/load exceptions, retained process state after a spawn failure,
the CLI's direct engine path, and whole-file WAV reads. A separate red test then
proved that auxiliary external outputs were not validated. During self-review,
another red test proved that a caller-supplied external workspace was not
rejected before cleanup. Each behavior was implemented only after its expected
failure was observed.

Focused green result after the first implementation cycle:

```text
9 passed in 0.08s
```

## Verification

```text
QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest tests/core tests/test_cli.py -q
158 passed, 1 warning in 7.27s

QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest tests/ui -q
141 passed in 2.87s

../../.venv/bin/python scripts/build_translations.py --check
exit 0

git diff --check
exit 0
```

The warning is the existing Python 3.12 `audioop` deprecation emitted by
`pydub`; it is unrelated to Task 2.

## Self-Review

- Regression: core, CLI, and the complete offscreen UI suite pass; Task 1 worker
  lifecycle and atomic publication tests remain green.
- Edge cases: incomplete/empty results, auxiliary outputs, partial model
  failure, external paths/workspaces, publication races, cross-device failure,
  process-start retry, cancellation, and bounded reads are covered.
- Security: cleanup is restricted to a validated hidden workspace directly
  below the requested output directory. The CLI no longer unlinks paths
  returned by a model.
- Side effects and idempotence: failed runs remove only their workspace and
  publish nothing; successful reruns fail closed if the destination song
  directory already exists rather than replacing user data.

## Remaining Concern

The native macOS `renamex_np(..., RENAME_EXCL)` publication path cannot be
executed on Linux and remains contingent on the macOS arm64 workflow.
