#!/usr/bin/env bash
# Build the Linux bundle with PyInstaller and run the --help smoke test.
set -euo pipefail

# Always operate from the project root, whatever the caller's cwd.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

# No local .venv in the packaging worktree: default to the root venv.
# Override with PYTHON=/path/to/python.
PYTHON="${PYTHON:-../../.venv/bin/python}"
PYINSTALLER_CONFIG_DIR="$ROOT_DIR/.cache/pyinstaller"
export PYINSTALLER_CONFIG_DIR

"$PYTHON" -m PyInstaller --noconfirm --clean packaging/stem-separator.spec

"$PYTHON" -m scripts.smoke_bundle dist/StemSeparator/_internal
QT_QPA_PLATFORM=offscreen dist/StemSeparator/StemSeparator --help
