# Task 2 Report: Naming Helpers

## Status

Implemented the CLI naming helpers in `separateur_de_stems/core/naming.py` with
the exact requested interfaces. Added focused tests in `tests/core/test_naming.py`.

## TDD Evidence

1. Added the required tests before production code.
2. Ran `../../.venv/bin/python -m pytest tests/core/test_naming.py -v` and observed
   collection fail with `ModuleNotFoundError: No module named
   'separateur_de_stems.core.naming'`.
3. Added the minimal implementation.
4. Re-ran the targeted suite: 8 tests passed.
5. Ran the complete suite: 8 tests passed.

## Implemented Behavior

- `sanitize` replaces every occurrence of `<>:"/\\|?*` with `_` while preserving
  spaces, accents, and all other characters.
- `unique_path` returns an available path unchanged and otherwise tries `_1`,
  `_2`, and subsequent numeric suffixes before the extension.
- `stem_filename` builds a complete path from sanitized source and stem names,
  normalizes extensions by removing leading dots, and applies `unique_path`.

## Self-review

- Security: no command execution, external input parsing, or path creation was
  added. `output_dir` remains caller-controlled by design.
- Side effects: helpers do not create or modify files. They only inspect path
  existence; repeated calls are stable while filesystem state remains unchanged.
- Idempotence/concurrency: availability checking and later file creation are not
  atomic, so concurrent writers can receive the same candidate path. Atomic file
  creation belongs to the future output-writing layer.
- Regression: the complete existing test suite passes.
- Edge cases and unexpected input: forbidden characters, spaces, accents,
  existing `_1` collisions, selection of `_2`, free paths, source colons, and
  extensions with a leading dot are covered. Empty names or extensions are not
  specified by the task and are not rejected.

## Verification

- Targeted: `8 passed in 0.02s`.
- Complete suite: `8 passed in 0.02s`.
- `git diff --check`: clean.

## Review Correction 1/5

### Changes

- Preserved the exact input string when `unique_path` receives an available
  path, including a leading `./`.
- Replaced target-following existence checks with `os.path.lexists`, so dangling
  symbolic links are treated as occupied for both the original path and numbered
  candidates.

### TDD and Verification

- Command: `../../.venv/bin/python -m pytest tests/core/test_naming.py -v`.
- RED output: `2 failed, 8 passed in 0.04s`; failures showed `./song.wav` being
  normalized and a dangling symlink being returned as available.
- GREEN targeted output: `10 passed in 0.02s`.
- Full-suite command: `../../.venv/bin/python -m pytest -v`.
- Full-suite output: `10 passed in 0.02s`.
- Commit: `fix(core): preserve paths and detect dangling symlinks`.

### Self-review

- The correction is limited to path availability detection and free-path return
  representation; existing suffix selection and filename construction remain
  unchanged.
- Security: dangling links can no longer be mistaken for free output names.
- Side effects and idempotence: the helper still only reads filesystem metadata
  and preserves repeatability while filesystem state is unchanged. The existing
  check-then-create concurrency race remains the output writer's responsibility.
- Unexpected inputs covered by this correction: explicitly relative free paths
  and dangling symbolic links. Symlink creation requires platform support and is
  exercised on the Linux development target.
