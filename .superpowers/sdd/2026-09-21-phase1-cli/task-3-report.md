# Task 3 report: errors and model selection

## TDD evidence

- RED 1: `../../.venv/bin/python -m pytest tests/core/test_models.py` failed during collection with `ModuleNotFoundError: separateur_de_stems.core.errors`.
- RED 2: after adding only the error hierarchy, the same command failed with `ModuleNotFoundError: separateur_de_stems.core.models`.
- GREEN: the targeted suite collected 16 tests and reported `16 passed in 0.02s`.
- REGRESSION: the full suite collected 26 tests and reported `26 passed in 0.03s`.

## Implementation

- Added the project error base and four required direct subclasses.
- Added exact supported extensions and stem-to-model mappings.
- Added frozen `ModelSpec` values with per-instance SDR copies and the required output metadata.
- Added deterministic selection, shared-model deduplication, empty-input handling, and sorted unknown-stem errors.

## Commit

- `feat(core): add error hierarchy and model selection` (this commit)

## Self-review

- Confirmed all six mappings, model filenames, output stems, and specified SDR values against the task brief.
- Confirmed model ordering does not depend on set iteration order.
- Confirmed unknown stems are validated before any partial result is returned.
- Confirmed caller-owned SDR dictionaries and separate `ModelSpec` instances do not share mutable state.
- No security-sensitive input, filesystem access, subprocess, network access, or secret handling was introduced.

## Risks, idempotence, and edge cases

- `ModelSpec` is shallowly frozen by design: its `sdr` dictionary remains mutable, but construction copies it to prevent cross-instance mutation. Callers can still mutate an individual specification.
- `select_models` is side-effect free and idempotent for the same input set.
- Covered empty input, one and multiple unknown stems, mixed known/unknown input, nondeterministic set ordering, and guitar/piano deduplication.
