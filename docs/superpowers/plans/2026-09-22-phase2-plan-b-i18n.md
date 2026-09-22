# Phase 2 — Plan B (i18n FR/EN) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre l'interface bilingue (anglais source, français traduit), chargée au lancement selon la préférence et appliquée à chaud sans redémarrage.

**Architecture:** Des données de traduction dans `separateur_de_stems/ui/i18n/` (`.ts` source + `.qm` compilé committé), un module `ui/i18n.py` qui résout la langue et installe/retire le `QTranslator`, un script `scripts/build_translations.py`, et des méthodes `retranslate_ui()` dans les fenêtres déclenchées par `QEvent.LanguageChange`. L'anglais est la langue source : seul un `.qm` FR est produit.

**Tech Stack:** Python 3.12, PySide6 6.11.2 (pyside6-lupdate/pyside6-lrelease), pytest-qt 4.5.0.

**Spec:** `docs/superpowers/specs/2026-09-22-phase2-plan-b-i18n-design.md`

## Global Constraints

- Anglais = langue source des chaînes `tr()` ; au moins un `.qm` FR.
- Aucune dépendance Qt dans `core/`.
- Tests headless : `QT_QPA_PLATFORM=offscreen` ; aucun réseau, aucune inférence.
- **La locale système de ce poste est le français** : tout test supposant une locale anglaise DOIT mocker `QLocale.system()`.
- Un commit par tâche ; hooks pre-commit/semgrep/gitleaks obligatoires.
- Ne pas traduire les messages `core`/CLI.
- Ne pas casser les tests existants (221 passed, 1 deselected).

---

### Task 1: Module i18n (`ui/i18n.py`) et résolution de langue

**Files:**
- Create: `separateur_de_stems/ui/i18n.py`
- Test: `tests/ui/test_i18n.py`

**Interfaces:**
- Consumes: `ui.paths.is_frozen`.
- Produces:
  - `available_languages() -> list[str]` → `["system", "fr"]`.
  - `i18n_dir() -> Path` — `ui/i18n/` en dev ; `sys._MEIPASS/separateur_de_stems/ui/i18n` en bundle.
  - `resolve_language(setting: str) -> str | None` — `"system"` → `"fr"` si la locale système est française sinon `None` ; `"fr"` → `"fr"` ; `"en"`/inconnu → `None`.
  - `install_translators(app, setting) -> str` — retire l'éventuel traducteur précédent, charge `stem_separator_fr.qm` si `resolve_language` renvoie `"fr"`, installe, retourne `"fr"` ou `"en"`. Conserve une référence au traducteur (module-level) pour éviter le GC.

- [ ] **Step 1: Écrire les tests qui échouent**

`tests/ui/test_i18n.py` :
```python
from pathlib import Path
from unittest import mock

import pytest
from PySide6.QtCore import QLocale

from separateur_de_stems.ui import i18n


def test_available_languages_contains_system_and_french():
    langs = i18n.available_languages()
    assert "system" in langs
    assert "fr" in langs


def test_resolve_explicit_french():
    assert i18n.resolve_language("fr") == "fr"


def test_resolve_explicit_english_is_none():
    assert i18n.resolve_language("en") is None


def test_resolve_system_french():
    with mock.patch.object(
        QLocale, "system", return_value=mock.Mock(
            language=mock.Mock(return_value=QLocale.Language.French)
        )
    ):
        assert i18n.resolve_language("system") == "fr"


def test_resolve_system_english_is_none():
    with mock.patch.object(
        QLocale, "system", return_value=mock.Mock(
            language=mock.Mock(return_value=QLocale.Language.English)
        )
    ):
        assert i18n.resolve_language("system") is None


def test_i18n_dir_exists_in_dev():
    assert (i18n.i18n_dir() / "stem_separator_fr.ts").is_file()


def test_install_translators_returns_effective_language(qtbot):
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    assert i18n.install_translators(app, "fr") == "fr"
    assert i18n.install_translators(app, "en") == "en"
```

- [ ] **Step 2: Lancer les tests pour vérifier l'échec**

Run: `cd "." && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ui/test_i18n.py -v`
Expected: FAIL (`ModuleNotFoundError`) — noter que `test_i18n_dir_exists_in_dev` échouera aussi tant que le `.ts` n'existe pas (créé en Task 2) ; il est acceptable que cette assertion échoue jusqu'à la Task 2, mais l'implémenteur doit créer un `.ts` minimal vide (squelette XML) pour rendre ce test vert, OU déplacer ce test en Task 2. Choisir : créer dans cette tâche un `i18n/stem_separator_fr.ts` minimal valide.

- [ ] **Step 3: Implémenter `ui/i18n.py`**

```python
"""Translation loading for the interface.

English is the source language, so only a French ``.qm`` is produced. The
setting can be ``"system"`` (follow the OS locale), ``"fr"`` or ``"en"``.
"""
from pathlib import Path

from PySide6.QtCore import QLocale, QTranslator

from separateur_de_stems.ui import paths

_QM_BASENAME = "stem_separator"
_FR_CODE = "fr"

_current_translator: QTranslator | None = None


def available_languages() -> list[str]:
    return ["system", "fr"]


def i18n_dir() -> Path:
    if paths.is_frozen():
        import sys

        return Path(sys._MEIPASS) / "separateur_de_stems" / "ui" / "i18n"
    return Path(__file__).resolve().parent / "i18n"


def _system_is_french() -> bool:
    return QLocale.system().language() == QLocale.Language.French


def resolve_language(setting: str) -> str | None:
    if setting == _FR_CODE:
        return _FR_CODE
    if setting == "system":
        return _FR_CODE if _system_is_french() else None
    return None


def install_translators(app, setting: str) -> str:
    global _current_translator
    if _current_translator is not None:
        app.removeTranslator(_current_translator)
        _current_translator = None

    language = resolve_language(setting)
    if language == _FR_CODE:
        translator = QTranslator()
        if translator.load(str(i18n_dir() / f"{_QM_BASENAME}_{_FR_CODE}.qm")):
            _current_translator = translator
            app.installTranslator(translator)
            return _FR_CODE
    return "en"
```
Créer aussi `separateur_de_stems/ui/i18n/stem_separator_fr.ts` minimal valide (squelette `<?xml ...?><TS version="2.1" language="fr_FR"></TS>`).

- [ ] **Step 4: Lancer les tests pour vérifier le succès**

Run: `cd "." && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ui/test_i18n.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add separateur_de_stems/ui/i18n.py separateur_de_stems/ui/i18n/stem_separator_fr.ts tests/ui/test_i18n.py
git commit -m "feat(ui): add i18n resolution and translator loading"
```

---

### Task 2: Script de build des traductions et compilation FR

**Files:**
- Create: `scripts/build_translations.py`
- Create: `scripts/__init__.py` (vide)
- Modify: `separateur_de_stems/ui/i18n/stem_separator_fr.ts` (traductions réelles)
- Create: `separateur_de_stems/ui/i18n/stem_separator_fr.qm` (généré)
- Test: `tests/ui/test_translations_build.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: `ui.i18n.i18n_dir`.
- Produces:
  - `source_files() -> list[str]` — fichiers `ui/*.py` à scanner.
  - `ts_path() -> str`, `qm_path() -> str`.
  - `build(check: bool = False) -> int` — exécute lupdate puis lrelease ; `check=True` n'écrit pas et échoue si les `.qm` changeraient.
  - `main(argv=None) -> int`.
- `pyproject.toml` : `[tool.setuptools.package-data]` inclut `separateur_de_stems.ui = ["i18n/*.qm", "i18n/*.ts"]`.

- [ ] **Step 1: Écrire les tests qui échouent**

```python
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import build_translations as bt


def test_source_files_lists_ui_modules():
    files = bt.source_files()
    assert any(f.endswith("main_window.py") for f in files)


def test_ts_and_qm_paths_are_under_i18n():
    assert bt.ts_path().endswith("stem_separator_fr.ts")
    assert bt.qm_path().endswith("stem_separator_fr.qm")


def test_build_compiles_into_temporary_copy(tmp_path):
    lrelease = bt._find_tool("pyside6-lrelease")
    if lrelease is None:
        pytest.skip("pyside6-lrelease unavailable")
    # copy the ts, compile to a temp qm, ensure valid output
    ts = Path(bt.ts_path())
    if not ts.is_file():
        pytest.skip("source ts missing")
    dest = tmp_path / "out.qm"
    result = subprocess.run(
        [lrelease, str(ts), "-qm", str(dest)],
        capture_output=True,
    )
    assert result.returncode == 0
    assert dest.stat().st_size > 0
```

- [ ] **Step 2: Lancer les tests pour vérifier l'échec**

Run: `cd "." && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ui/test_translations_build.py -v`
Expected: FAIL (module inexistant).

- [ ] **Step 3: Implémenter `scripts/build_translations.py`**

```python
"""Regenerate the Qt translation files (.ts and .qm)."""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UI_DIR = ROOT / "separateur_de_stems" / "ui"
I18N_DIR = UI_DIR / "i18n"
BASENAME = "stem_separator"
LANGUAGES = ["fr"]


def source_files() -> list[str]:
    return sorted(str(path) for path in UI_DIR.glob("*.py"))


def ts_path(language: str = "fr") -> str:
    return str(I18N_DIR / f"{BASENAME}_{language}.ts")


def qm_path(language: str = "fr") -> str:
    return str(I18N_DIR / f"{BASENAME}_{language}.qm")


def _find_tool(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    candidate = Path(sys.executable).parent / name
    if candidate.is_file():
        return str(candidate)
    return None


def build(check: bool = False) -> int:
    lupdate = _find_tool("pyside6-lupdate")
    lrelease = _find_tool("pyside6-lrelease")
    if lupdate is None or lrelease is None:
        print("pyside6-lupdate/pyside6-lrelease not found", file=sys.stderr)
        return 1

    for language in LANGUAGES:
        ts = ts_path(language)
        if not check:
            update = subprocess.run(
                [lupdate, *source_files(), "-ts", ts], capture_output=True
            )
            if update.returncode != 0:
                print(update.stdout.decode(), update.stderr.decode(), file=sys.stderr)
                return update.returncode
        qm = qm_path(language)
        if check:
            target = Path(qm).with_suffix(".check.qm")
        else:
            target = Path(qm)
        release = subprocess.run(
            [lrelease, ts, "-qm", str(target)], capture_output=True
        )
        if release.returncode != 0:
            print(release.stdout.decode(), release.stderr.decode(), file=sys.stderr)
            return release.returncode
        if check:
            changed = target.read_bytes() != Path(qm).read_bytes()
            target.unlink(missing_ok=True)
            if changed:
                print(f"{qm} is out of date", file=sys.stderr)
                return 1
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build Qt translations.")
    parser.add_argument("--check", action="store_true",
                        help="Fail if .qm files are out of date (no write).")
    args = parser.parse_args(argv)
    return build(check=args.check)


if __name__ == "__main__":
    sys.exit(main())
```
Écrire les traductions françaises réelles dans `stem_separator_fr.ts` (au minimum
les chaînes des tâches suivantes ; lupdate complétera). Puis exécuter le script
pour générer `stem_separator_fr.qm`.

- [ ] **Step 4: Lancer les tests pour vérifier le succès**

Run: `cd "." && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ui/test_translations_build.py -v`
Expected: 3 passed (skips acceptés si outil absent, mais l'outil est présent).

- [ ] **Step 5: Commit**

```bash
git add scripts pyproject.toml separateur_de_stems/ui/i18n tests/ui/test_translations_build.py
git commit -m "feat(i18n): add translation build script and compiled French catalog"
```

---

### Task 3: Traductions françaises complètes

**Files:**
- Modify: `separateur_de_stems/ui/i18n/stem_separator_fr.ts`
- Modify: `separateur_de_stems/ui/i18n/stem_separator_fr.qm` (régénéré)
- Test: `tests/ui/test_i18n_integration.py`

**Interfaces:**
- Consumes: `ui.i18n.install_translators`, `scripts.build_translations`.
- Produces: `.qm` contenant les traductions réelles ; test qui prouve le chargement.

- [ ] **Step 1: Extraire toutes les chaînes**

Run: `cd "." && .venv/bin/python scripts/build_translations.py`
Puis remplir les traductions FR manquantes dans `stem_separator_fr.ts` (inclure les 53 chaînes de `drop_zone.py`, `main_window.py`, `settings_dialog.py`). Régénérer `.qm`.

- [ ] **Step 2: Écrire le test d'intégration**

```python
import pytest
from PySide6.QtWidgets import QApplication

from separateur_de_stems.ui import i18n
from separateur_de_stems.ui.main_window import MainWindow


def test_french_translation_changes_known_text(qtbot):
    app = QApplication.instance()
    effective = i18n.install_translators(app, "fr")
    assert effective == "fr"
    # "Separate" is a known UI string; French catalog must translate it.
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.tr("Separate") != "Separate"
    i18n.install_translators(app, "en")
```

- [ ] **Step 3: Lancer le test pour vérifier le succès**

Run: `cd "." && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ui/test_i18n_integration.py -v`
Expected: 1 passed.

- [ ] **Step 4: Commit**

```bash
git add separateur_de_stems/ui/i18n/stem_separator_fr.ts separateur_de_stems/ui/i18n/stem_separator_fr.qm tests/ui/test_i18n_integration.py
git commit -m "feat(i18n): complete French translations and add integration test"
```

---

### Task 4: Application à chaud (`retranslate_ui`)

**Files:**
- Modify: `separateur_de_stems/ui/drop_zone.py`
- Modify: `separateur_de_stems/ui/main_window.py`
- Modify: `separateur_de_stems/ui/settings_dialog.py`
- Test: `tests/ui/test_retranslate.py`

**Interfaces:**
- Consumes: `i18n.install_translators`.
- Produces:
  - `DropZone.retranslate_ui()`.
  - `MainWindow.retranslate_ui()` ; `changeEvent` sur `LanguageChange`.
  - `SettingsDialog.languageChanged = Signal(str)` ; `SettingsDialog.retranslate_ui()`.
  - `MainWindow.open_settings()` applique la langue à l'acceptation.

- [ ] **Step 1: Écrire les tests qui échouent**

```python
import pytest
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication

from separateur_de_stems.ui import i18n
from separateur_de_stems.ui.main_window import MainWindow
from separateur_de_stems.ui.settings import Settings


@pytest.fixture
def isolated_settings():
    store = Settings(organization="TestOrg", application="TestApp")
    store.clear()
    yield store
    store.clear()


def test_retranslate_updates_button_text(qtbot, isolated_settings):
    app = QApplication.instance()
    window = MainWindow(settings=isolated_settings)
    qtbot.addWidget(window)
    english = window.separate_button.text()
    i18n.install_translators(app, "fr")
    window.retranslate_ui()
    assert window.separate_button.text() != english
    i18n.install_translators(app, "en")
    window.retranslate_ui()
    assert window.separate_button.text() == english


def test_language_change_event_triggers_retranslate(qtbot, isolated_settings):
    app = QApplication.instance()
    window = MainWindow(settings=isolated_settings)
    qtbot.addWidget(window)
    english = window.windowTitle()
    i18n.install_translators(app, "fr")
    window.changeEvent(QEvent(QEvent.Type.LanguageChange))
    assert window.windowTitle() != english
    i18n.install_translators(app, "en")
```

- [ ] **Step 2: Lancer les tests pour vérifier l'échec**

Run: `cd "." && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ui/test_retranslate.py -v`
Expected: FAIL (`retranslate_ui` absent).

- [ ] **Step 3: Implémenter**

Ajouter `retranslate_ui()` aux trois widgets, en y déplaçant/réappliquant tous les
libellés (`self.tr(...)`). `MainWindow.changeEvent` appelle `retranslate_ui()` sur
`LanguageChange`. `SettingsDialog.open`/`accept` émet `languageChanged(str)` si la
langue change effectivement. `MainWindow.open_settings()` connecte ce signal à
`install_translators`.

- [ ] **Step 4: Lancer les tests pour vérifier le succès**

Run: `cd "." && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ui/test_retranslate.py -v`
Expected: 2 passed.

- [ ] **Step 5: Lancer la suite complète**

Run: `cd "." && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q`
Expected: tous passent (E2E slow exclu).

- [ ] **Step 6: Commit**

```bash
git add separateur_de_stems/ui/drop_zone.py separateur_de_stems/ui/main_window.py separateur_de_stems/ui/settings_dialog.py tests/ui/test_retranslate.py
git commit -m "feat(i18n): apply language change live via retranslate_ui"
```

---

### Task 5: Intégration du choix de langue au lancement

**Files:**
- Modify: `separateur_de_stems/ui/app.py`
- Modify: `separateur_de_stems/ui/settings_dialog.py` (si besoin)
- Test: `tests/ui/test_app_smoke.py` (étendu)

**Interfaces:**
- Consumes: `i18n.install_translators`, `Settings`.
- Produces: `app.main()` installe la langue mémorisée au démarrage.

- [ ] **Step 1: Écrire le test qui échoue**

Étendre `tests/ui/test_app_smoke.py` : vérifier que `main([])` appelle
`install_translators` (monkeypatch pour espionner) et que la langue mémorisée
est utilisée.

- [ ] **Step 2: Lancer le test pour vérifier l'échec**

Run: `cd "." && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ui/test_app_smoke.py -v`
Expected: FAIL sur le nouveau test.

- [ ] **Step 3: Implémenter**

Dans `app.main`, après avoir créé `QApplication` et lu `Settings`, appeler
`i18n.install_translators(app, settings.language)` avant de construire
`MainWindow`.

- [ ] **Step 4: Lancer la suite complète**

Run: `cd "." && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q`
Expected: tous passent.

- [ ] **Step 5: Commit**

```bash
git add separateur_de_stems/ui/app.py tests/ui/test_app_smoke.py
git commit -m "feat(i18n): load saved language at startup"
```

---

## Self-Review

**1. Spec coverage**
- Dossier `ui/i18n/`, `.ts` + `.qm` committés (spec §2, §3.1) → Tasks 1-3.
- `i18n.py` : `available_languages`/`i18n_dir`/`resolve_language`/`install_translators` (spec §3.2) → Task 1.
- Anglais source, seul `.qm` FR (spec §2) → Tasks 1-3.
- « Système » via `QLocale` (spec §2) → Task 1.
- Application à chaud + `retranslate_ui` (spec §4) → Task 4.
- Script de build + package-data (spec §5) → Task 2.
- Tests i18n, intégration `.qm`, build, retranslate (spec §6) → Tasks 1-5. ✓
- Démarrage avec la langue mémorisée (spec §4) → Task 5. ✓
- Hors périmètre core/CLI, autres langues (spec §7) → non implémentés. ✓

**2. Placeholder scan**
Aucun `TBD`/`TODO`. La Task 2 contient le code complet du script. Les traductions
FR (Task 3) sont un contenu à remplir mais la liste des sources est explicite
(`ui/*.py`) et le test d'intégration prouve le résultat.

**3. Type consistency**
- `i18n_dir() -> Path` : Task 1, consommé Task 1/2.
- `install_translators(app, setting) -> str` : Task 1, consommé Tasks 3/4/5.
- `resolve_language(setting) -> str | None` : Task 1, consommé Task 1.
- `build(check) -> int`, `source_files`, `ts_path`, `qm_path` : Task 2, consommé Task 2/3.
- `languageChanged = Signal(str)` : Task 4, consommé Task 4.
- `retranslate_ui()` : Task 4, consommé Task 4.

**Note d'exécution** : ce plan est plus court que le Plan A ; chaque tâche reste
testable headless et fusionnable seule.
