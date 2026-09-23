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
