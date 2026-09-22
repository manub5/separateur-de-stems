# Hardening And Offline Release Design

## Goal

Make the application safe against data loss, keep the Qt event loop responsive,
make cancellation and shutdown deterministic, provide actionable failures, and
produce a reproducible macOS bundle that contains every selected model and
ffmpeg dependency required for offline use.

## Runtime Architecture

Each UI run owns an immutable `RunContext` containing input, output, model
directory, requested stems, and a private temporary workspace. The worker
process performs separation and exports final WAV/MP3 files before emitting a
terminal result. The GUI never scans output trees, converts audio, waits on a
process, or derives paths from mutable widgets after a run starts.

All temporary model outputs live below the private workspace. Success moves
only complete deliverables into the song output directory; failure,
cancellation, and shutdown remove only the private workspace. Existing user
files are never inferred from directory snapshots and never deleted.

Cancellation is a request, not a blocking GUI operation. The worker thread
observes the request, terminates the child, emits one terminal signal, and then
finishes. The window remains locked until `QThread.finished`; closing an active
window requests cancellation and defers close until the thread exits.

## Validation And Errors

Input paths must be readable regular files with a supported extension. Output
and model directories are validated before starting. Catalogue construction,
model loading, separation, and export failures are translated into project
exceptions with useful context. A successful result must contain every
requested stem and every declared output must exist.

WAV conversion uses bounded-memory block processing. MP3 encoding remains an
argument-list subprocess and becomes cancellable in the background execution
path. Progress reserves its final range for exports.

## Packaging And Offline Data

The selected model files, their configuration files, and
`download_checks.json` are mandatory build inputs and are copied under
`models/`. The PyInstaller spec fails if required models, ffmpeg, or ffprobe are
missing or non-executable. Runtime paths use bundled models by default while a
validated user override remains supported.

The macOS workflow uses locked direct versions, verifies arm64 ffmpeg/ffprobe,
runs offline synthetic smoke checks against the bundle, declares minimal token
permissions, measures artifact size, and emits a SHA-256 checksum. Public tag
artifacts remain disabled until all model and redistributed-binary licences are
recorded as distributable.

## Compatibility And Documentation

Python metadata is bounded to the verified compatibility range. Test-only
dependencies are explicit. Device selection is either passed through a
documented `audio-separator` API or described as delegated to that library; no
dead accelerator promise remains.

`README.md`, `MODELS.md`, `QUESTIONS.md`, `DECISIONS.md`, and `PROGRESS.md` must
describe the implemented behavior without claiming completion while licences
or macOS runtime validation remain unresolved.

## Testing

Tests cover immutable run context, attempts to change input/output while
running, cancellation and close, thread lifecycle, incomplete results, model
directory settings, absent/unreadable inputs, invalid output directories,
bounded WAV conversion, process-start cleanup, categorized model failures,
confined intermediate cleanup, strict packaging inputs, workflow permissions,
and offline bundle smoke commands. Synthetic audio is used throughout.

The full offscreen suite, slow E2E suite, translation freshness check,
pre-commit, semgrep, and gitleaks must pass before completion. Real MPS/CoreML
and the final `.app` remain explicitly contingent on the macOS arm64 workflow.
