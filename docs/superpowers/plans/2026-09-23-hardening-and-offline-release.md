# Hardening And Offline Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve every verified review finding and leave a safe, responsive, offline-capable release candidate.

**Architecture:** A frozen per-run context and private workspace replace mutable-widget state and directory snapshots. Separation plus export run outside the GUI; packaging validates and embeds all offline assets before producing an artifact.

**Tech Stack:** Python 3.12, PySide6, multiprocessing spawn, audio-separator 0.47.0, soundfile, ffmpeg, PyInstaller, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-23-hardening-and-offline-release-design.md`

## Global Constraints

- Work only inside the project; dependencies, models, and caches remain local.
- Use synthetic audio for tests and never train or invent a separation model.
- Preserve existing CLI/UI behavior unless it is unsafe or contradicts AGENTS.md.
- TDD for every behavior change; one local commit per completed task.
- No public artifact until model and redistributed-binary licences are verified.

---

### Task 1: Safe UI Run Lifecycle

**Files:**
- Create: `separateur_de_stems/ui/run_context.py`
- Modify: `separateur_de_stems/ui/main_window.py`
- Modify: `separateur_de_stems/ui/worker.py`
- Test: `tests/ui/test_main_window.py`
- Test: `tests/ui/test_worker.py`

**Interfaces:**
- Produces: immutable `RunContext(input_path: str, output_dir: str, model_dir: str, stems: frozenset[str], workspace: str)`.
- Produces: non-blocking `SeparationWorker.request_cancel()` and one terminal outcome followed by native `finished`.

- [x] Add failing tests for changing input/output during a run, active close, immediate relaunch, configured model directory, empty output, absent input, incomplete outputs, and non-blocking cancellation.
- [x] Confirm each new test fails for the reviewed reason.
- [x] Implement immutable run state, disable all mutable controls/actions, defer close until native thread completion, and validate inputs/output/model directory.
- [x] Remove snapshot-based cleanup and delete only the run workspace.
- [x] Keep the UI locked until native `QThread.finished`, then release/delete the worker and complete deferred close.
- [x] Run `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ui -q` and commit `fix(ui): make run lifecycle safe and non-blocking`.

### Task 2: Background Export And Robust Engine

**Files:**
- Create: `separateur_de_stems/core/pipeline.py`
- Modify: `separateur_de_stems/core/engine.py`
- Modify: `separateur_de_stems/core/export.py`
- Modify: `separateur_de_stems/core/process.py`
- Modify: `separateur_de_stems/cli.py`
- Modify: `separateur_de_stems/ui/worker.py`
- Test: `tests/core/test_pipeline.py`
- Test: `tests/core/test_engine.py`
- Test: `tests/core/test_export.py`
- Test: `tests/core/test_process.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: `run_pipeline(input_path, stems, output_dir, model_dir, *, include_mp3=True, progress_cb=None) -> dict[str, list[str]]`.
- Produces: block-based `to_wav24`; confined temporary cleanup; categorized catalogue/model errors.

- [x] Add failing tests for bounded reads, incomplete outputs, extra model outputs, partial failures, external-path preservation, spawn failure reset, catalogue/load failures, and export progress.
- [x] Confirm failures, then implement a private workspace pipeline that exports before returning and cleans in `finally`.
- [x] Make `Process.start()` transactional and cancellation repeatable without GUI waits.
- [x] Centralize confined cleanup; remove duplicated unsafe CLI/UI cleanup.
- [x] Use structured progress stages and map errors to project exceptions.
- [x] Run core and CLI tests and commit `fix(core): isolate runs and harden separation exports`.

### Task 3: Strict Offline Packaging

**Files:**
- Modify: `separateur_de_stems/ui/paths.py`
- Modify: `separateur_de_stems/core/platform.py`
- Modify: `packaging/stem-separator.spec`
- Modify: `packaging/build_linux.sh`
- Modify: `.github/workflows/build-macos.yml`
- Modify: `pyproject.toml`
- Create: `requirements/macos-arm64.lock`
- Test: `tests/packaging/test_spec.py`
- Test: `tests/packaging/test_workflow.py`
- Test: `tests/packaging/test_build_linux.py`
- Test: `tests/ui/test_paths.py`

**Interfaces:**
- Produces: one executable-checked bundled ffmpeg resolver and bundled `models/` runtime path.
- Requires: every filename in `STEM_TO_MODEL`, associated configuration, and `download_checks.json` at build time.

- [x] Add failing tests requiring model data, ffmpeg/ffprobe build failures, executable checks, Python upper bound, explicit PyYAML, workflow permissions/checksum/size/offline smoke, and locked installs.
- [x] Make the spec fail fast and include offline data; centralize runtime path resolution.
- [x] Bound Python compatibility and declare every direct development dependency.
- [x] Add a hash-ready macOS lock input and remove unconstrained pip upgrades/Homebrew ambiguity where feasible.
- [x] Add bundle inspection and synthetic ffmpeg smoke steps; gate tag publication on a licence manifest.
- [x] Run packaging tests and commit `fix(packaging): enforce reproducible offline bundles`.

### Task 4: Documentation, Licences, And Release State

**Files:**
- Modify: `README.md`
- Modify: `MODELS.md`
- Modify: `QUESTIONS.md`
- Modify: `DECISIONS.md`
- Modify: `PROGRESS.md`
- Modify: `PLAN.md`
- Create: `THIRD_PARTY_NOTICES.md`
- Test: `tests/packaging/test_readme.py`

**Interfaces:**
- Produces: accurate bilingual operational and release documentation.

- [x] Add failing documentation tests for offline models, responsive export/cancel wording, licence gate, Python range, and macOS validation limitations.
- [x] Record exact local model sizes/checksums and only licenses supported by verified bundled metadata; mark unknown licenses as release blockers rather than guessing.
- [x] Align progress/questions/decisions with actual completion and remaining external validation.
- [x] Run documentation tests and commit `docs: align release documentation with hardened behavior`.

### Task 5: Full Quality Gate

**Files:**
- Modify only files required by failures discovered in this task.

- [ ] Run `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q`.
- [ ] Run `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -m slow -q`.
- [ ] Run `.venv/bin/python scripts/build_translations.py --check`.
- [ ] Run `PRE_COMMIT_HOME="$PWD/.cache/pre-commit" pre-commit run --all-files`.
- [ ] Build the Linux bundle and inspect ffmpeg, ffprobe, translations, and all selected model assets.
- [ ] Smoke-test the frozen binary in an environment without system ffmpeg and with network access disabled where supported.
- [ ] Review the full branch against the spec, fix only verified regressions, rerun affected and full checks, then commit any final correction.
