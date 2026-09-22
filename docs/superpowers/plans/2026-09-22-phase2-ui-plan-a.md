# Phase 2 — Plan A (UI PySide6) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fournir une interface de bureau PySide6 (fenêtre unique, drag&drop, choix des pistes, progression, annulation) branchée sur le moteur `core` de la phase 1, testable en headless.

**Architecture:** Un paquet `ui/` sans logique métier qui pilote `SubprocessSeparator` (déjà testé) depuis un `QThread`, traduit les statuts en signaux Qt, et compose `core` (engine/models/export/errors). Trois ajouts bornés à `core/process.py` (garde de re-entrée, drain robuste, queue de progression). Aucune dépendance Qt dans `core/`.

**Tech Stack:** Python 3.12, PySide6 6.11.2, pytest-qt 4.5.0, `audio-separator` 0.47.0 (déjà installé).

**Spec:** `docs/superpowers/specs/2026-09-22-phase2-ui-design.md`

## Global Constraints

- Commentaires et noms de code : **anglais**. Chaînes UI dans `self.tr("...")` **en anglais** dès maintenant (prêtes pour l'i18n du Plan B).
- Aucune dépendance Qt dans `core/` ni `cli.py`.
- Tests UI headless : `QT_QPA_PLATFORM=offscreen` ; aucun test ne lance d'inférence réelle.
- Python 3.12 ; dépendances uniquement dans `.venv/` local ; jamais de `sudo`/`apt`.
- Un commit par tâche ; hooks pre-commit/semgrep/gitleaks doivent passer.
- Sorties : WAV 24 bits + MP3 320 par piste, dans un **sous-dossier par morceau**.
- Progression **par étape/modèle** uniquement.
- Chemins dev : `./models`, `./.cache` ; en bundle : dossier utilisateur via `QStandardPaths`.
- NE PAS réécrire `core` au-delà des trois ajouts listés en Task 2.

---

### Task 1: Dépendances UI et squelette du paquet `ui/`

**Files:**
- Modify: `pyproject.toml`
- Create: `separateur_de_stems/ui/__init__.py`
- Create: `tests/ui/__init__.py`
- Modify: `PROGRESS.md`

**Interfaces:**
- Consumes: rien.
- Produces: paquet importable `separateur_de_stems.ui` ; dépendances `PySide6`, `pytest-qt` déclarées.

- [ ] **Step 1: Déclarer les dépendances**

Dans `pyproject.toml`, ajouter :
```toml
dependencies = [
    "audio-separator",
    "soundfile",
    "PySide6",
]

[project.optional-dependencies]
dev = ["pytest", "pytest-qt"]
```
Ne pas changer `addopts`, `testpaths`, `pythonpath`.

- [ ] **Step 2: Créer les paquets**

`separateur_de_stems/ui/__init__.py` :
```python
"""PySide6 desktop interface for the stem separator."""
```

`tests/ui/__init__.py` : fichier vide.

- [ ] **Step 3: Vérifier l'import**

Run: `cd "." && QT_QPA_PLATFORM=offscreen .venv/bin/python -c "import separateur_de_stems.ui; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Mettre à jour PROGRESS.md**

Ajouter une section « Phase 2 (UI) » avec « Plan A en cours ».

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml separateur_de_stems/ui/__init__.py tests/ui/__init__.py PROGRESS.md
git commit -m "chore(ui): add PySide6 dependencies and ui package skeleton"
```

---

### Task 2: Ajouts bornés à `core/process.py`

**Files:**
- Modify: `separateur_de_stems/core/process.py`
- Modify: `tests/core/test_process.py`

**Interfaces:**
- Consumes: `SubprocessSeparator` existant.
- Produces:
  - `SubprocessSeparator(engine_kwargs, worker_target=None, context=None, worker_args=(), progress_queue=None)`.
  - `start()` lève `RuntimeError` si un run est déjà en cours (re-entrée).
  - Si `progress_queue` fournie, le worker par défaut y dépose `(percent: int, stage: str)` pendant la séparation ; le parent peut les lire via `poll_progress() -> list[tuple[int, str]]`.
  - Le drain n'utilise plus un timeout fixe fragile.

- [ ] **Step 1: Écrire les tests qui échouent**

Le fichier de test existe déjà (phase 1) ; il définit des workers de module
picklables. Ajouter à la fin de `tests/core/test_process.py` :

```python
def _sleeping_progress_worker(queue, input_path, stems, delay, progress_queue=None):
    """Module-level worker (picklable) that reports progress then sleeps."""
    import time

    if progress_queue is not None:
        progress_queue.put((10, "Loading model"))
        progress_queue.put((50, "Separating"))
    time.sleep(delay)
    queue.put(("ok", {"vocals": "out.wav"}))


def test_start_twice_raises_runtime_error():
    sep = SubprocessSeparator(
        engine_kwargs={},
        worker_target=_sleeping_progress_worker,
        worker_args=(1.0,),
    )
    sep.start("in.wav", {"vocals"})
    try:
        with pytest.raises(RuntimeError):
            sep.start("in.wav", {"vocals"})
    finally:
        sep.cancel()


def test_poll_progress_collects_worker_messages():
    queue = multiprocessing.get_context("spawn").Queue()
    sep = SubprocessSeparator(
        engine_kwargs={},
        worker_target=_sleeping_progress_worker,
        worker_args=(0.3,),
        progress_queue=queue,
    )
    sep.start("in.wav", {"vocals"})
    collected = []
    deadline = time.time() + 5.0
    while time.time() < deadline and not collected:
        collected.extend(sep.poll_progress())
        time.sleep(0.05)
    sep.cancel()
    assert (10, "Loading model") in collected
    assert (50, "Separating") in collected
    queue.close()


def test_run_without_progress_queue_still_returns_result():
    sep = SubprocessSeparator(
        engine_kwargs={},
        worker_target=_sleeping_progress_worker,
        worker_args=(0.1,),
    )
    result = sep.run("in.wav", {"vocals"})
    assert result == {"vocals": "out.wav"}
```

Contraintes des helpers : fonctions de **module** (picklables pour `spawn`),
signature `(queue, input_path, stems, *worker_args)`. La `progress_queue` est
ajoutée par le `SubprocessSeparator` quand elle est fournie, donc le worker
reçoit un paramètre nommé optionnel `progress_queue=None`.

- [ ] **Step 2: Lancer les tests pour vérifier l'échec**

Run: `cd "." && .venv/bin/python -m pytest tests/core/test_process.py -v`
Expected: FAIL sur les nouveaux tests (re-entrée non gardée, `poll_progress` absent).

- [ ] **Step 3: Implémenter**

Dans `core/process.py` :
- Ajouter `progress_queue=None` au constructeur.
- Dans `start()`, passer la `progress_queue` au worker **comme argument nommé**
  (`progress_queue=self._progress_queue`) en plus des `worker_args`, afin que
  le `worker_target` injecté en test reçoive le même canal que le worker par
  défaut.
- Dans `_default_worker`, si `progress_queue` est fournie, passer un
  `progress_cb` à `engine.run` qui fait `progress_queue.put((percent, stage))`.
- Ajouter `poll_progress()` qui vide `self._progress_queue` sans blocage
  (`get_nowait` en boucle, `queue.Empty` → stop) et retourne
  `list[tuple[int, str]]` ; retourne `[]` si aucune queue n'est configurée.
- Garde de re-entrée dans `start()` : si `self._process is not None`, lever
  `RuntimeError("separation already running")`.
- Fiabiliser le drain : après `is_alive()` False, boucler sur
  `queue.get(timeout=...)` avec un budget global plutôt qu'un unique timeout
  fixe de 1 s ; en cas d'échec, message d'erreur inchangé.
- Fermer proprement la `progress_queue` dans les chemins de fin/annulation.
- Ne pas modifier l'API utilisée par la CLI (paramètres par défaut compatibles).

- [ ] **Step 4: Lancer les tests pour vérifier le succès**

Run: `cd "." && .venv/bin/python -m pytest tests/core/test_process.py -v`
Expected: tous passent, y compris les tests phase 1 (régression).

- [ ] **Step 5: Lancer la suite complète**

Run: `cd "." && .venv/bin/python -m pytest -q`
Expected: tous les tests passent (E2E slow exclu).

- [ ] **Step 6: Commit**

```bash
git add separateur_de_stems/core/process.py tests/core/test_process.py
git commit -m "feat(core): add subprocess re-entry guard, robust drain and progress queue"
```

---

### Task 3: Résolution des chemins (`ui/paths.py`)

**Files:**
- Create: `separateur_de_stems/ui/paths.py`
- Test: `tests/ui/test_paths.py`

**Interfaces:**
- Consumes: rien (stdlib + PySide6 `QStandardPaths`).
- Produces:
  - `is_frozen() -> bool` — vrai dans un bundle PyInstaller (`sys.frozen`).
  - `default_model_dir() -> str`, `default_cache_dir() -> str` — `./models`, `./.cache` en dev ; sous-dossier `StemSeparator` de `QStandardPaths.AppDataLocation` en bundle.
  - `default_output_dir() -> str` — `QStandardPaths.MusicLocation` (ou `DocumentsLocation` en repli), sinon `Path.home()`.
  - `ffmpeg_dir() -> str | None` — dossier contenant ffmpeg embarqué (`sys._MEIPASS`) ou `None` si non embarqué.

- [ ] **Step 1: Écrire les tests qui échouent**

```python
import sys
from unittest import mock
from separateur_de_stems.ui import paths


def test_dev_model_dir_is_relative_models(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert paths.default_model_dir() == "models"


def test_frozen_model_dir_is_under_appdata(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    value = paths.default_model_dir()
    assert value.endswith("models")
    assert "StemSeparator" in value


def test_default_output_dir_non_empty():
    assert paths.default_output_dir()
```

- [ ] **Step 2: Lancer les tests pour vérifier l'échec**

Run: `cd "." && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ui/test_paths.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implémenter `ui/paths.py`**

```python
"""Path resolution for development and frozen (.app) builds."""
import os
import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths

APP_DIR_NAME = "StemSeparator"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _app_data_dir() -> Path:
    base = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppDataLocation
    )
    return Path(base) / APP_DIR_NAME


def default_model_dir() -> str:
    if is_frozen():
        return str(_app_data_dir() / "models")
    return "models"


def default_cache_dir() -> str:
    if is_frozen():
        return str(_app_data_dir() / "cache")
    return ".cache"


def default_output_dir() -> str:
    for location in (
        QStandardPaths.StandardLocation.MusicLocation,
        QStandardPaths.StandardLocation.DocumentsLocation,
    ):
        value = QStandardPaths.writableLocation(location)
        if value:
            return value
    return str(Path.home())


def ffmpeg_dir() -> str | None:
    if is_frozen() and hasattr(sys, "_MEIPASS"):
        candidate = Path(sys._MEIPASS) / "ffmpeg"
        if candidate.exists():
            return str(candidate)
    return None
```

- [ ] **Step 4: Lancer les tests pour vérifier le succès**

Run: `cd "." && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ui/test_paths.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add separateur_de_stems/ui/paths.py tests/ui/test_paths.py
git commit -m "feat(ui): add development and frozen path resolution"
```

---

### Task 4: Préférences (`ui/settings.py`)

**Files:**
- Create: `separateur_de_stems/ui/settings.py`
- Test: `tests/ui/test_settings.py`

**Interfaces:**
- Consumes: rien.
- Produces:
  - `Settings` classe encapsulant `QSettings("StemSeparator", "StemSeparator")`.
  - Propriétés : `language: str` (défaut `"system"`), `last_input_dir: str` (défaut `""`), `output_dir: str` (défaut `""` → l'appelant utilise `default_output_dir()`), `model_dir: str`, `default_stems: list[str]` (défaut `["vocals", "instrumental"]`).
  - `save()`/relecture immédiate cohérente.
  - Utiliser une organisation/application de test pour ne pas polluer la config réelle (`QSettings.setDefaultFormat` ou clé d'app paramétrable) — easier: accepter `organization`/`application` en paramètres avec défauts, les tests injectent des valeurs isolées et appellent `clear()`.

- [ ] **Step 1: Écrire les tests qui échouent**

```python
from separateur_de_stems.ui.settings import Settings


def test_defaults(qtbot):
    s = Settings(organization="TestOrg", application="TestApp")
    s.clear()
    assert s.language == "system"
    assert s.default_stems == ["vocals", "instrumental"]


def test_roundtrip(qtbot):
    s = Settings(organization="TestOrg", application="TestApp")
    s.clear()
    s.language = "fr"
    s.default_stems = ["vocals", "drums"]
    assert s.language == "fr"
    assert s.default_stems == ["vocals", "drums"]


def test_output_dir_default_empty(qtbot):
    s = Settings(organization="TestOrg", application="TestApp")
    s.clear()
    assert s.output_dir == ""
```

- [ ] **Step 2: Lancer les tests pour vérifier l'échec**

Run: `cd "." && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ui/test_settings.py -v`
Expected: FAIL (module inexistant).

- [ ] **Step 3: Implémenter `ui/settings.py`**

Implémenter une classe `Settings` avec un `QSettings` interne, des propriétés typées, et `clear()`. Stocker `default_stems` comme liste via une valeur séparée par des virgules (`",".join` / `split`). Ne jamais écrire hors du `QSettings` natif.

- [ ] **Step 4: Lancer les tests pour vérifier le succès**

Run: `cd "." && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ui/test_settings.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add separateur_de_stems/ui/settings.py tests/ui/test_settings.py
git commit -m "feat(ui): add QSettings-backed preferences"
```

---

### Task 5: Worker Qt (`ui/worker.py`)

**Files:**
- Create: `separateur_de_stems/ui/worker.py`
- Test: `tests/ui/test_worker.py`

**Interfaces:**
- Consumes: `SubprocessSeparator`, `core.errors`.
- Produces:
  - `SeparationWorker(QThread)` construite avec `(input_path, stems, output_dir, model_dir, separator_factory=None)`.
  - Signaux : `progress = Signal(int, str)`, `finished = Signal(dict)`, `failed = Signal(str)`, `cancelled = Signal()`.
  - `request_cancel()` thread-safe.
  - `run()` : crée un `SubprocessSeparator` (injectable pour tests), démarre, boucle de poll (pas ~0.1 s), relit `poll_progress()` → `progress.emit`, puis émet le signal final correspondant. N'accède à aucun widget.
  - Distingue annulation (`cancelled`) / erreur (`failed`) / succès (`finished`).
  - **Relocalisation des sorties** : regroupe les fichiers produits dans `output_dir/<morceau>/` (le worker ou l'appelant ; trancher ici : le worker retourne le dict brut, le regroupement se fait dans `MainWindow` via `core.export`/`naming` — garder le worker mince, donc le worker retourne le dict brut).

- [ ] **Step 1: Écrire les tests qui échouent**

Utiliser un faux `SubprocessSeparator` injectable :
```python
import time
from separateur_de_stems.ui.worker import SeparationWorker


class FakeSep:
    def __init__(self, *a, **k):
        self.started = False
    def start(self, input_path, stems, progress_cb=None):
        self.started = True
    def poll(self, timeout=0):
        return ("ok", {"vocals": "/tmp/v.wav"})
    def cancel(self):
        pass
    def poll_progress(self):
        return [(50, "Separating vocals")]


def test_worker_emits_finished(qtbot):
    worker = SeparationWorker(
        "in.wav", {"vocals"}, "/out", "models",
        separator_factory=lambda **k: FakeSep(),
    )
    with qtbot.waitSignal(worker.finished, timeout=2000) as sig:
        worker.start()
    assert sig.args[0] == {"vocals": "/tmp/v.wav"}


def test_worker_emits_failed(qtbot):
    class FailSep(FakeSep):
        def poll(self, timeout=0):
            return ("error", "boom")
    worker = SeparationWorker(
        "in.wav", {"vocals"}, "/out", "models",
        separator_factory=lambda **k: FailSep(),
    )
    with qtbot.waitSignal(worker.failed, timeout=2000) as sig:
        worker.start()
    assert "boom" in sig.args[0]
```
Ajouter un test `cancelled` et un test qui vérifie l'émission de `progress`.

- [ ] **Step 2: Lancer les tests pour vérifier l'échec**

Run: `cd "." && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ui/test_worker.py -v`
Expected: FAIL (module inexistant).

- [ ] **Step 3: Implémenter `ui/worker.py`**

`SeparationWorker(QThread)` avec les signaux ci-dessus, `run()` en boucle `while self._running`, `poll(timeout=0.1)`, `poll_progress()`, gestion `CancelledError`/`StemSeparatorError`, `request_cancel()` mettant un flag et appelant `sep.cancel()`. Aucun import de widgets Qt (uniquement `QtCore`).

- [ ] **Step 4: Lancer les tests pour vérifier le succès**

Run: `cd "." && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ui/test_worker.py -v`
Expected: tous passent.

- [ ] **Step 5: Commit**

```bash
git add separateur_de_stems/ui/worker.py tests/ui/test_worker.py
git commit -m "feat(ui): add QThread separation worker with signals"
```

---

### Task 6: Zone de dépôt (`ui/drop_zone.py`)

**Files:**
- Create: `separateur_de_stems/ui/drop_zone.py`
- Test: `tests/ui/test_drop_zone.py`

**Interfaces:**
- Consumes: `core.models.SUPPORTED_EXTENSIONS`.
- Produces:
  - `DropZone(QFrame)` avec signal `fileDropped = Signal(str)`.
  - `set_file(path: str | None)` met à jour l'affichage.
  - `current_file() -> str | None`.
  - Accepte le drag&drop ; ignore les formats non supportés (signal `invalidDropped = Signal(str)` facultatif, ou ignore silencieusement — trancher : émettre `fileRejected = Signal(str)`).

- [ ] **Step 1: Écrire les tests qui échouent**

Simuler un `QDropEvent` avec des URLs locales (`QUrl.fromLocalFile`), vérifier l'émission de `fileDropped` pour `.wav`, et `fileRejected` pour `.ogg`. Vérifier `set_file`/`current_file`.

- [ ] **Step 2: Lancer les tests pour vérifier l'échec**

Run: `cd "." && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ui/test_drop_zone.py -v`
Expected: FAIL (module inexistant).

- [ ] **Step 3: Implémenter `ui/drop_zone.py`**

`QFrame` avec `setAcceptDrops(True)`, `dragEnterEvent`/`dropEvent`, `QLabel` interne, style via `setFrameStyle`/feuille de style minimale. Vérifier l'extension via `os.path.splitext(path)[1].lower() in SUPPORTED_EXTENSIONS`.

- [ ] **Step 4: Lancer les tests pour vérifier le succès**

Run: `cd "." && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ui/test_drop_zone.py -v`
Expected: tous passent.

- [ ] **Step 5: Commit**

```bash
git add separateur_de_stems/ui/drop_zone.py tests/ui/test_drop_zone.py
git commit -m "feat(ui): add drag and drop zone"
```

---

### Task 7: Fenêtre principale (`ui/main_window.py`) et entrée (`ui/app.py`)

**Files:**
- Create: `separateur_de_stems/ui/main_window.py`
- Create: `separateur_de_stems/ui/app.py`
- Test: `tests/ui/test_main_window.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: `DropZone`, `Settings`, `SeparationWorker`, `ui.paths`, `core.export`, `core.naming`, `core.models`.
- Produces:
  - `MainWindow(settings: Settings | None = None)` ; widget racine.
  - `open_file(path)` ; `start_separation()` ; `on_progress(int, str)` ; `on_finished(dict)` ; `on_failed(str)` ; `on_cancelled()`.
  - `build_parser`/`main` dans `app.py` avec `--file` optionnel ; `[project.scripts] separateur-de-stems-ui = "separateur_de_stems.ui.app:main"`.
  - Regroupement des sorties dans `<output>/<morceau>/` avec WAV 24 bits + MP3 320 par piste (via `to_wav24`/`to_mp3_320` de `core.export` et `stem_filename`).

- [ ] **Step 1: Écrire les tests qui échouent**

Tests headless sans inférence (worker mocké) :
```python
def test_main_window_constructs(qtbot):
    from separateur_de_stems.ui.main_window import MainWindow
    w = MainWindow()
    qtbot.addWidget(w)
    assert w.windowTitle()
    assert not w.separate_button.isEnabled()


def test_piste_selection_enables_button(qtbot, tmp_path):
    from separateur_de_stems.ui.main_window import MainWindow
    w = MainWindow()
    qtbot.addWidget(w)
    w.open_file(str(tmp_path / "x.wav"))  # nécessite un fichier? accepter chemin sans lecture
    assert w.separate_button.isEnabled()
```
Ajouter un test du passage de l'état « en cours » (bouton devient Annuler), un test `on_finished` écrivant les fichiers via mocks d'export, et un test d'erreur. Adapter les noms d'attributs à l'implémentation.

- [ ] **Step 2: Lancer les tests pour vérifier l'échec**

Run: `cd "/home/mb_.../Séparateur_de_stems" && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ui/test_main_window.py -v`
Expected: FAIL (module inexistant).

- [ ] **Step 3: Implémenter la fenêtre**

Composer la disposition de la section 4 du spec : zone de dépôt + « Ouvrir… », 6 cases, dossier de sortie + « Choisir… », bouton Séparer/Annuler, barre de progression + libellé, journal, menus. Toutes les chaînes en `self.tr("English text")`. État des boutons selon fichier/pistes. Lancer `SeparationWorker`, brancher les signaux, désactiver les entrées pendant l'exécution, gérer terminé/erreur/annulé. Regrouper les sorties dans un sous-dossier par morceau. Ne pas bloquer l'UI.

- [ ] **Step 4: Implémenter `app.py`**

`main(argv=None)` crée `QApplication`, applique le style par défaut, instancie `MainWindow`, lit `--file` éventuel, `sys.exit(app.exec())`. Déclarer la cible console dans `pyproject.toml`.

- [ ] **Step 5: Lancer les tests pour vérifier le succès**

Run: `cd "." && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ui/test_main_window.py -v`
Expected: tous passent.

- [ ] **Step 6: Lancer la suite complète**

Run: `cd "." && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q`
Expected: tous passent (E2E slow exclu).

- [ ] **Step 7: Commit**

```bash
git add separateur_de_stems/ui/main_window.py separateur_de_stems/ui/app.py tests/ui/test_main_window.py pyproject.toml
git commit -m "feat(ui): add compact main window and app entry point"
```

---

### Task 8: Réglages (`ui/settings_dialog.py`) et intégration

**Files:**
- Create: `separateur_de_stems/ui/settings_dialog.py`
- Test: `tests/ui/test_settings_dialog.py`
- Modify: `separateur_de_stems/ui/main_window.py`

**Interfaces:**
- Consumes: `Settings`, `ui.paths`.
- Produces:
  - `SettingsDialog(settings)` — dossier de modèles, langue (« Système », « English », « Français »), bouton « Clear cache » (supprime le contenu de `default_cache_dir()` après confirmation).
  - Intégration dans le menu « Edit > Settings » de `MainWindow`.

- [ ] **Step 1: Écrire les tests qui échouent**

Vérifier la construction du dialogue, le roundtrip des champs vers `Settings`, et que le bouton cache appelle bien la suppression (mock/`tmp_path`).

- [ ] **Step 2: Lancer les tests pour vérifier l'échec**

Run: `cd "." && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ui/test_settings_dialog.py -v`
Expected: FAIL (module inexistant).

- [ ] **Step 3: Implémenter et intégrer**

`SettingsDialog(QDialog)` avec `QLineEdit` + bouton parcourir pour les modèles, `QComboBox` langue, bouton cache. `accept()` écrit dans `Settings`. Ajouter l'action de menu dans `MainWindow`.

- [ ] **Step 4: Lancer les tests pour vérifier le succès**

Run: `cd "." && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ui/test_settings_dialog.py -v`
Expected: tous passent.

- [ ] **Step 5: Commit**

```bash
git add separateur_de_stems/ui/settings_dialog.py tests/ui/test_settings_dialog.py separateur_de_stems/ui/main_window.py
git commit -m "feat(ui): add settings dialog and menu integration"
```

---

### Task 9: Test de fumée de l'application et mise à jour documentaire

**Files:**
- Create: `tests/ui/test_app_smoke.py`
- Modify: `PROGRESS.md`, `DECISIONS.md`

**Interfaces:**
- Consumes: `ui.app.main`.
- Produces: preuve que l'application démarre en offscreen sans inférence.

- [ ] **Step 1: Écrire le test de fumée**

Lancer `app.py` en mode offscreen avec un timer qui quitte, ou tester `MainWindow` + `QApplication` complet. Vérifier qu'aucune exception ne remonte et que la fenêtre apparaît.

- [ ] **Step 2: Lancer le test**

Run: `cd "." && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ui/test_app_smoke.py -v`
Expected: 1 passed.

- [ ] **Step 3: Mettre à jour la documentation**

`PROGRESS.md` : Plan A terminé. `DECISIONS.md` : D-008 (QThread pilote `SubprocessSeparator`), D-009 (pytest-qt + offscreen).

- [ ] **Step 4: Lancer la suite complète et vérifier le lancement réel**

Run: `cd "." && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q`
Expected: tous passent.

Puis, si possible, lancer brièvement l'appli réelle (sans écran) pour confirmer l'absence de crash :
`QT_QPA_PLATFORM=offscreen .venv/bin/python -m separateur_de_stems.ui.app --help`

- [ ] **Step 5: Commit**

```bash
git add tests/ui/test_app_smoke.py PROGRESS.md DECISIONS.md
git commit -m "test(ui): add application smoke test and update docs"
```

---

## Self-Review

**1. Spec coverage**
- Fenêtre unique compacte (spec §4) → Tasks 6, 7. ✓
- Drag&drop + formats (spec §4.1) → Task 6. ✓
- Choix des pistes, défaut, dédup modèles (spec §4.2) → Task 7. ✓
- Dossier de sortie + sous-dossier par morceau (spec §4.3, §2) → Task 7. ✓
- Bouton Séparer→Annuler, états (spec §4.4) → Tasks 5, 7. ✓
- Progression par étape + journal (spec §4.5) → Tasks 2, 5, 7. ✓
- Menus + Réglages + langue stockée (spec §4.6, §6) → Tasks 4, 8. ✓
- Worker QThread + signaux, annulation (spec §5) → Tasks 2, 5. ✓
- Ajouts `core` bornés (spec §5) → Task 2. ✓
- QSettings + chemins adaptatifs (spec §6) → Tasks 3, 4. ✓
- Chaînes en `tr()` prêtes i18n (spec §6) → Task 7. ✓
- Tests headless pytest-qt, pas d'inférence (spec §8) → Tasks 3-9. ✓
- Entrée `separateur-de-stems-ui` (spec §7) → Task 7. ✓
- i18n extraction/packaging PyInstaller → **hors Plan A** (Plans B et C). ✓

**2. Placeholder scan**
Aucun `TBD`/`TODO`. Certains tests (Task 2, 5, 6, 7, 8) décrivent le comportement et les noms d'attributs à retenir tout en laissant l'implémenteur écrire le test exact — c'est intentionnel car l'API UI est définie dans cette même tâche ; les valeurs de l'interface (`Signal(int,str)`, chemins, signaux) sont explicites.

**3. Type consistency**
- `SubprocessSeparator(..., progress_queue=None)` + `poll_progress()` : défini Task 2, consommé Task 5. ✓
- `Settings(organization, application)` : défini Task 4, consommé Tasks 7, 8. ✓
- `SeparationWorker(input_path, stems, output_dir, model_dir, separator_factory)` : défini Task 5, consommé Task 7. ✓
- `DropZone.fileDropped`/`fileRejected` : défini Task 6, consommé Task 7. ✓
- `MainWindow` : Task 7, étendu Task 8. ✓
- `paths.default_model_dir/default_cache_dir/default_output_dir/ffmpeg_dir` : Task 3, consommés Tasks 4, 7, 8. ✓

**Note d'exécution** : le Plan A est volumineux (9 tâches) ; c'est le découpage minimal où chaque tâche est testable headless et fusionnable indépendamment.
