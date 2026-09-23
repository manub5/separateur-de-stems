# Task 3 Report — Strict Offline Packaging

## Status

Implemented. Development paths remain usable and the distributable build now
fails clearly because the selected offline model manifest is incomplete.

## Changes

- Added a machine-readable manifest covering every unique `STEM_TO_MODEL`
  filename. Unknown payload/config/checksum/licence data remains explicit.
- Added bounded-memory manifest validation and a strict packaging gate for
  models, configs, checks metadata, translations, ffmpeg and ffprobe.
- Centralized executable ffmpeg resolution (`is_file` and `X_OK`).
- Made frozen default model resolution conditional on a complete, distributable
  `_MEIPASS/models` manifest; development and user overrides stay explicit.
- Added post-build asset inspection and synthetic WAV-to-MP3 smoke with an
  empty system `PATH`.
- Hardened macOS CI permissions, pinned direct requirements, arm64 media-tool
  checks, artifact sizing and SHA-256 output.
- Bounded Python support to the locally verified 3.12 line and declared PyYAML
  as a development dependency.

## Tests

- `python -m pytest tests/packaging tests/core/test_platform.py tests/ui/test_paths.py -q`
  — 72 passed, 1 deselected.
- `python -m PyInstaller --noconfirm --clean packaging/stem-separator.spec`
  — expected failure before Analysis: manifest fields for the vocals model are
  unknown; no full bundle was built.
- `python -m scripts.smoke_bundle --help` — passed, confirming module invocation.

## Concerns

- No model payload or licence was downloaded or inferred. Release remains
  blocked until all manifest fields and files are supplied and verified.
- macOS bundle layout, arm64 binaries, MPS/CoreML and the final smoke remain
  unverified locally and require the macOS arm64 workflow.
- Direct macOS requirements are version-pinned but do not claim a fully hashed
  transitive lock.

## Review Round 1

- Manifest validation now requires exactly the unique `STEM_TO_MODEL` files,
  declares `download_checks.json`, rejects duplicate models, and validates all
  field types, positive sizes and 64-character lowercase SHA-256 values.
- The translation gate requires a non-empty `stem_separator_fr.qm`.
- The redundant UI `ffmpeg_dir` resolver was removed; executable resolution
  remains centralized in `core.platform` with `is_file` and `X_OK` checks.
- Added a separate ffmpeg/ffprobe redistribution-licence manifest. Unknown
  licence data blocks both strict builds and tagged release validation.
- Renamed the macOS input to `requirements/macos-arm64.lock` and documented it
  as a strict direct inventory only. Tagged releases require a separate hashed
  transitive lock generated and validated on macOS arm64; none was fabricated
  on Linux and the workflow does not use `--require-hashes` without one.
- Replaced the mocked smoke subprocess with controlled executable scripts that
  prove `PATH` is empty and that missing MP3 output fails.

Review verification:

- `python -m pytest tests/packaging tests/core/test_platform.py tests/ui/test_paths.py -q`
  — 86 passed, 1 deselected.
- `python -m pytest -q` with `QT_QPA_PLATFORM=offscreen`
  — 352 passed, 2 deselected.
