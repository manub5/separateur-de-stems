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

## Review Fix Round 1

- Separator construction and `load_model()` now have distinct
  `ModelUnavailableError` messages that identify the failed boundary and model.
- Every native no-replace publication `OSError`, including destination races and
  cross-device failures, is converted to contextual `OutputError` with the
  native exception retained as `__cause__`.
- The terminal 100% progress notification is explicitly best-effort after the
  atomic commit. An observer failure can no longer report failure after outputs
  have already been published.
- The external-output pipeline regression now returns an actual external model
  output and verifies `OutputError`, no publication, preservation of the
  external file, and workspace cleanup.
- Successful progress coverage verifies ordered `export.wav`/`export.mp3`
  stages in 81–99 and one terminal 100 event only after the final directory is
  visible.
- Auxiliary-output confinement now uses existing internal and external files,
  preserves both sources, and verifies that no deliverable is produced.
- Removed the unused CLI `_ensure_output_dir`, `Path`, and `OutputError` import.

TDD red verification produced the three expected failures: factory errors were
reported as load failures, native publication leaked `OSError`, and a throwing
terminal observer converted an already-published success into failure. Focused
green verification:

```text
../../.venv/bin/python -m pytest \
  tests/core/test_engine.py::test_engine_maps_separator_factory_failure_to_model_error \
  tests/core/test_engine.py::test_engine_maps_load_model_failure_to_model_error \
  tests/core/test_engine.py::test_engine_rejects_any_auxiliary_output_outside_private_directory \
  tests/core/test_pipeline.py::test_pipeline_partial_failure_publishes_nothing_and_preserves_external_path \
  tests/core/test_pipeline.py::test_pipeline_wraps_native_publication_failure_as_output_error \
  tests/core/test_pipeline.py::test_terminal_progress_failure_does_not_turn_published_success_into_failure \
  tests/core/test_pipeline.py::test_pipeline_reports_ordered_export_progress_only_before_terminal_success -q
7 passed in 0.05s
```

Affected-suite verification before final gate:

```text
QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest \
  tests/core/test_engine.py tests/core/test_pipeline.py tests/test_cli.py \
  tests/ui/test_worker.py -q
86 passed in 2.91s
```

Final gate before commit:

```text
Affected suite: 86 passed in 3.56s
Core + CLI + complete offscreen UI suite: 302 passed, 1 warning in 9.20s
Translation freshness check: exit 0
git diff --check: exit 0
```

The warning remains the pre-existing Python 3.12 `audioop` deprecation from
`pydub`.
