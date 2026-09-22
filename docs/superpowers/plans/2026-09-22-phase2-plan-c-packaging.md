# Phase 2 — Plan C (packaging) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produire un exécutable Linux testé localement et un `.app` macOS Apple Silicon construit par GitHub Actions, avec un README bilingue, en emballant toutes les dépendances sauf les modèles.

**Architecture:** Un spec PyInstaller (`packaging/stem-separator.spec`) qui collecte PySide6, audio-separator, torch/onnxruntime, soundfile et les données i18n, et copie ffmpeg dans le bundle. Un `runtime_hook.py` pour `multiprocessing.freeze_support()`. `core/export.py` résout le ffmpeg embarqué via un helper Qt-free. Un workflow macOS arm64. Un README bilingue.

**Tech Stack:** Python 3.12, PyInstaller 6.22.3, PySide6 6.11.2, audio-separator 0.47.0, ffmpeg.

**Spec:** `docs/superpowers/specs/2026-09-22-phase2-plan-c-packaging-design.md`

## Global Constraints

- Modèles **hors bundle** ; données audio-separator embarquées.
- `core/` reste Qt-free : résoudre ffmpeg embarqué sans importer `PySide6`.
- Tests headless (`QT_QPA_PLATFORM=offscreen`) ; pas d'inférence, pas de réseau.
- Un commit par tâche ; hooks pre-commit/semgrep/gitleaks obligatoires.
- Ne pas casser les 267 tests existants.
- macOS non testable localement : le workflow fait office de test, documenté.

---

### Task 1: Résolution du ffmpeg embarqué dans `core/`

**Files:**
- Modify: `separateur_de_stems/core/platform.py`
- Modify: `separateur_de_stems/core/export.py`
- Test: `tests/core/test_platform.py`, `tests/core/test_export.py`

**Interfaces:**
- Consumes: rien.
- Produces:
  - `core.platform.ffmpeg_executable() -> str` — retourne le chemin de ffmpeg embarqué (`<sys._MEIPASS>/ffmpeg/ffmpeg`) s'il existe, sinon `"ffmpeg"` (PATH). Qt-free.
  - `core.export.to_mp3_320` utilise `ffmpeg_executable()` au lieu de `which("ffmpeg")`.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `tests/core/test_platform.py` :
```python
import sys
from unittest import mock


def test_ffmpeg_executable_prefers_bundled(monkeypatch, tmp_path):
    from separateur_de_stems.core import platform as plat

    bundled = tmp_path / "ffmpeg"
    bundled.mkdir()
    exe = bundled / "ffmpeg"
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert plat.ffmpeg_executable() == str(exe)


def test_ffmpeg_executable_falls_back_to_path(monkeypatch):
    from separateur_de_stems.core import platform as plat

    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    assert plat.ffmpeg_executable() == "ffmpeg"
```
Ajouter à `tests/core/test_export.py` :
```python
def test_to_mp3_uses_resolved_ffmpeg(tmp_path, monkeypatch):
    from separateur_de_stems.core import export
    captured = {}

    class Result:
        stderr = b""

    def fake_run(args, **kwargs):
        captured["args"] = args
        with open(args[-1], "wb") as handle:
            handle.write(b"mp3")
        return Result()

    monkeypatch.setattr(export, "ffmpeg_executable", lambda: "/bundle/ffmpeg")
    monkeypatch.setattr(export.subprocess, "run", fake_run)
    source = tmp_path / "src.wav"
    source.write_bytes(b"wav")
    export.to_mp3_320(str(source), str(tmp_path / "out.mp3"))
    assert captured["args"][0] == "/bundle/ffmpeg"
```

- [ ] **Step 2: Lancer les tests pour vérifier l'échec**

Run: `cd "." && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/core/test_platform.py tests/core/test_export.py -v`
Expected: FAIL (`ffmpeg_executable` absent, `export.ffmpeg_executable` non importé).

- [ ] **Step 3: Implémenter**

Dans `core/platform.py`, ajouter :
```python
def ffmpeg_executable() -> str:
    """Return the bundled ffmpeg path when frozen, else 'ffmpeg' from PATH."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidate = Path(meipass) / "ffmpeg" / "ffmpeg"
        if candidate.is_file():
            return str(candidate)
    return "ffmpeg"
```
(Ajouter `from pathlib import Path` et `import sys` si absents.)
Dans `core/export.py`, remplacer l'import `which`/ligne ffmpeg :
```python
from separateur_de_stems.core.platform import ffmpeg_executable
...
ffmpeg = ffmpeg_executable()
```

- [ ] **Step 4: Lancer les tests pour vérifier le succès**

Run: `cd "." && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/core/test_platform.py tests/core/test_export.py -v`
Expected: tous passent.

- [ ] **Step 5: Suite complète**

Run: `cd "." && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q`
Expected: tous passent.

- [ ] **Step 6: Commit**

```bash
git add separateur_de_stems/core/platform.py separateur_de_stems/core/export.py tests/core/test_platform.py tests/core/test_export.py
git commit -m "feat(core): resolve bundled ffmpeg for frozen builds"
```

---

### Task 2: Spec PyInstaller et runtime hook

**Files:**
- Create: `packaging/stem-separator.spec`
- Create: `packaging/runtime_hook.py`
- Test: `tests/packaging/__init__.py`, `tests/packaging/test_spec.py`
- Modify: `.gitignore` (ignorer `packaging/build/`, `packaging/dist/`)

**Interfaces:**
- Consumes: `separateur_de_stems/ui/app.py` (entrée), `separateur_de_stems/ui/i18n/*.qm`.
- Produces: spec exécutable par `pyinstaller`.

- [ ] **Step 1: Écrire les tests qui échouent**

`tests/packaging/test_spec.py` :
```python
from pathlib import Path

SPEC = Path("packaging/stem-separator.spec")
RUNTIME_HOOK = Path("packaging/runtime_hook.py")


def test_spec_exists():
    assert SPEC.is_file()


def test_runtime_hook_calls_freeze_support():
    text = RUNTIME_HOOK.read_text()
    assert "freeze_support" in text


def test_spec_collects_i18n_and_audio_separator():
    text = SPEC.read_text()
    assert "audio_separator" in text
    assert "i18n" in text
    assert "ffmpeg" in text
```

- [ ] **Step 2: Lancer les tests pour vérifier l'échec**

Run: `cd "." && .venv/bin/python -m pytest tests/packaging/test_spec.py -v`
Expected: FAIL (fichiers absents).

- [ ] **Step 3: Créer `packaging/runtime_hook.py`**

```python
"""PyInstaller runtime hook: make frozen multiprocessing spawn safe."""
import multiprocessing

multiprocessing.freeze_support()
```

- [ ] **Step 4: Créer `packaging/stem-separator.spec`**

```python
# -*- mode: python ; coding: utf-8 -*-
import os
import shutil
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

ROOT = Path(SPECPATH).parent.parent
APP_NAME = "StemSeparator"

datas = []
datas += collect_data_files("audio_separator")
datas += collect_data_files("separateur_de_stems")

hiddenimports = []
hiddenimports += collect_submodules("torch")
for module in ("audio_separator.separator", "onnxruntime", "soundfile", "librosa"):
    try:
        hiddenimports += collect_submodules(module)
    except Exception:
        pass

binaries = []
binaries += collect_dynamic_libs("onnxruntime")

ffmpeg_src = shutil.which("ffmpeg")
if ffmpeg_src:
    binaries.append((ffmpeg_src, "ffmpeg"))
ffprobe_src = shutil.which("ffprobe")
if ffprobe_src:
    binaries.append((ffprobe_src, "ffmpeg"))

excludes = [
    "tkinter", "matplotlib", "pytest", "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore", "PySide6.QtCharts",
]

a = Analysis(
    [str(ROOT / "separateur_de_stems" / "ui" / "app.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[str(ROOT / "packaging" / "runtime_hook.py")],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name=APP_NAME)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        bundle_identifier="com.example.stemseparator",
        info_plist={"NSHighResolutionCapable": True},
    )
```

- [ ] **Step 5: Mettre à jour `.gitignore`**

Ajouter `packaging/build/` et `packaging/dist/` (ou `build/`/`dist/` déjà présents — vérifier qu'ils couvrent `packaging/**/build`). `build/` et `dist/` existent déjà en racine ; PyInstaller les crée à la racine par défaut, donc rien de plus n'est nécessaire. Ajouter tout de même `*.spec` ? NON : le spec est versionné. Juste confirmer `build/`, `dist/`.

- [ ] **Step 6: Lancer les tests pour vérifier le succès**

Run: `cd "." && .venv/bin/python -m pytest tests/packaging/test_spec.py -v`
Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
git add packaging tests/packaging .gitignore
git commit -m "feat(packaging): add PyInstaller spec and runtime hook"
```

---

### Task 3: Build Linux et smoke test

**Files:**
- Create: `packaging/build_linux.sh`
- Test: `tests/packaging/test_build_linux.py`

**Interfaces:**
- Consumes: `packaging/stem-separator.spec`.
- Produces: `packaging/build_linux.sh` exécutable ; le binaire `dist/StemSeparator/StemSeparator`.

- [ ] **Step 1: Écrire le test qui échoue**

```python
from pathlib import Path

import pytest


def test_build_script_exists_and_is_executable():
    script = Path("packaging/build_linux.sh")
    assert script.is_file()


@pytest.mark.slow
def test_bundled_binary_help_runs():
    import subprocess

    binary = Path("dist/StemSeparator/StemSeparator")
    if not binary.is_file():
        pytest.skip("bundle not built; run packaging/build_linux.sh first")
    result = subprocess.run([str(binary), "--help"], capture_output=True)
    assert result.returncode == 0
```

- [ ] **Step 2: Lancer le test pour vérifier l'échec**

Run: `cd "." && .venv/bin/python -m pytest tests/packaging/test_build_linux.py -v`
Expected: `test_build_script_exists_and_is_executable` FAIL ; le test `slow` est désélectionné.

- [ ] **Step 3: Créer `packaging/build_linux.sh`**

```bash
#!/usr/bin/env bash
# Build the Linux bundle and run a smoke test. Development helper.
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-.venv/bin/python}"
"$PYTHON" -m PyInstaller --noconfirm --clean packaging/stem-separator.spec
QT_QPA_PLATFORM=offscreen "dist/StemSeparator/StemSeparator" --help >/dev/null
echo "Bundle built and smoke-tested: dist/StemSeparator/"
```
Rendre exécutable : `chmod +x packaging/build_linux.sh`.

- [ ] **Step 4: Lancer le test pour vérifier le succès**

Run: `cd "." && .venv/bin/python -m pytest tests/packaging/test_build_linux.py -v`
Expected: 1 passed, 1 deselected.

- [ ] **Step 5: Construire réellement le bundle (local)**

Run: `cd "." && bash packaging/build_linux.sh`
Expected: build termine, smoke `--help` code 0. Consigner dans le rapport la taille de `dist/StemSeparator/` et les éventuels `hiddenimports` ajoutés pour corriger des erreurs d'import.

- [ ] **Step 6: Lancer le smoke test marqué slow**

Run: `cd "." && .venv/bin/python -m pytest tests/packaging/test_build_linux.py -v -m slow`
Expected: 1 passed.

- [ ] **Step 7: Commit**

```bash
git add packaging/build_linux.sh tests/packaging/test_build_linux.py
git commit -m "feat(packaging): add Linux build script and binary smoke test"
```

---

### Task 4: Workflow GitHub Actions macOS

**Files:**
- Create: `.github/workflows/build-macos.yml`
- Test: `tests/packaging/test_workflow.py`

**Interfaces:**
- Consumes: `packaging/stem-separator.spec`, `scripts/build_translations.py`.
- Produces: workflow CI macOS arm64.

- [ ] **Step 1: Écrire le test qui échoue**

```python
from pathlib import Path

import yaml

WORKFLOW = Path(".github/workflows/build-macos.yml")


def test_workflow_exists_and_is_valid_yaml():
    data = yaml.safe_load(WORKFLOW.read_text())
    assert "jobs" in data


def test_workflow_uses_macos_arm_runner_and_builds_app():
    text = WORKFLOW.read_text()
    assert "macos-14" in text
    assert "pyinstaller" in text.lower()
    assert "build_translations" in text
    assert "upload-artifact" in text
```

- [ ] **Step 2: Lancer le test pour vérifier l'échec**

Run: `cd "." && .venv/bin/python -m pytest tests/packaging/test_workflow.py -v`
Expected: FAIL (fichier absent).

- [ ] **Step 3: Créer `.github/workflows/build-macos.yml`**

```yaml
name: Build macOS app

on:
  workflow_dispatch:
  push:
    tags:
      - "v*"

jobs:
  build:
    runs-on: macos-14
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install ffmpeg
        run: brew install ffmpeg
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install "PySide6" "audio-separator" "soundfile" "pytest" "pytest-qt" "pyinstaller"
      - name: Run tests
        run: QT_QPA_PLATFORM=offscreen python -m pytest -m "not slow" -q
      - name: Check translations
        run: python scripts/build_translations.py --check
      - name: Build app
        run: python -m PyInstaller --noconfirm --clean packaging/stem-separator.spec
      - name: Smoke test
        run: |
          QT_QPA_PLATFORM=offscreen "dist/StemSeparator.app/Contents/MacOS/StemSeparator" --help
      - name: Package
        run: |
          cd dist
          ditto -c -k --sequesterRsrc --keepParent "StemSeparator.app" "StemSeparator-macos.zip"
      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: StemSeparator-macos
          path: dist/StemSeparator-macos.zip
```
NOTE : sur macOS, le binaire de `EXE`/`COLLECT` est `dist/StemSeparator/StemSeparator` et le `BUNDLE` crée `dist/StemSeparator.app`. Vérifier le chemin réel lors de la première exécution CI ; ajuster le smoke test si besoin.

- [ ] **Step 4: Lancer le test pour vérifier le succès**

Run: `cd "." && .venv/bin/python -m pytest tests/packaging/test_workflow.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/build-macos.yml tests/packaging/test_workflow.py
git commit -m "ci: add macOS Apple Silicon build workflow"
```

---

### Task 5: README bilingue et mise à jour documentaire

**Files:**
- Create: `README.md`
- Modify: `PROGRESS.md`, `DECISIONS.md`, `PLAN.md`
- Test: `tests/packaging/test_readme.py`

**Interfaces:**
- Consumes: rien.
- Produces: `README.md` bilingue.

- [ ] **Step 1: Écrire le test qui échoue**

```python
from pathlib import Path

README = Path("README.md")


def test_readme_exists_and_is_bilingual():
    text = README.read_text()
    assert "Français" in text or "French" in text
    assert "English" in text
    assert "Ouvrir quand même" in text
```

- [ ] **Step 2: Lancer le test pour vérifier l'échec**

Run: `cd "." && .venv/bin/python -m pytest tests/packaging/test_readme.py -v`
Expected: FAIL (fichier absent).

- [ ] **Step 3: Écrire `README.md`**

Contenu bilingue couvrant : présentation, prérequis (Python 3.12, ffmpeg en dev), installation, CLI, UI, traductions, build PyInstaller Linux et macOS, procédure de premier lancement macOS non signé (« Ouvrir quand même » + mot de passe), crédits UVR. Deux sections : française puis anglaise.

- [ ] **Step 4: Mettre à jour la documentation projet**

`PROGRESS.md` : Plan C terminé. `DECISIONS.md` : D-011 (PyInstaller onedir, modèles hors bundle, ffmpeg embarqué, artefacts + repli Release). `PLAN.md` : cocher les étapes 6-8.

- [ ] **Step 5: Lancer les tests pour vérifier le succès**

Run: `cd "." && .venv/bin/python -m pytest tests/packaging/test_readme.py -v`
Expected: 1 passed.

- [ ] **Step 6: Suite complète**

Run: `cd "." && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q`
Expected: tous passent.

- [ ] **Step 7: Commit**

```bash
git add README.md PROGRESS.md DECISIONS.md PLAN.md tests/packaging/test_readme.py
git commit -m "docs: add bilingual README and finish packaging docs"
```

---

## Self-Review

**1. Spec coverage**
- Spec PyInstaller (spec §4) → Task 2. ✓
- ffmpeg embarqué + résolution core (spec §5) → Task 1. ✓
- Build Linux + smoke (spec §2, §8) → Task 3. ✓
- Workflow macOS (spec §6) → Task 4. ✓
- README bilingue (spec §7) → Task 5. ✓
- Tests packaging (spec §8) → Tasks 2-5. ✓
- Modèles hors bundle (spec §2, §9) → confirmé dans le spec PyInstaller.
- Exclusions Qt/upx (spec §4, §9) → Task 2.
- Hors périmètre (signature, Release auto) → non implémentés, documentés. ✓

**2. Placeholder scan**
Aucun `TBD`/`TODO`. Le spec PyInstaller (Task 2) contient le code complet. La
note « vérifier le chemin réel lors de la première exécution CI » n'est pas un
placeholder de plan mais une consigne d'exécution conditionnelle (macOS non
testable localement), explicitée.

**3. Type consistency**
- `ffmpeg_executable() -> str` (core/platform) : Task 1, consommé Task 1.
- `packaging/stem-separator.spec` : Task 2, consommé Tasks 3/4.
- `scripts/build_translations.py --check` : existant (Plan B), consommé Task 4.
- `README.md` : Task 5.

**Note d'exécution** : le build PyInstaller local (Task 3) peut être long (torch) ;
les `hiddenimports` seront probablement à itérer jusqu'au smoke test vert — c'est
attendu et testable.
