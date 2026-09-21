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
