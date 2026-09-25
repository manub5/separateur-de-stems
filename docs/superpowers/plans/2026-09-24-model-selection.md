# Sélection complète des modèles — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fournir tous les actifs et la sélection pour six pistes, avec téléchargements sûrs et build macOS personnel contrôlé.

**Architecture:** Le manifeste relie pistes, modèles et actifs hashés ; un téléchargeur reprend seulement les réponses HTTP Range conformes. L'interface exploite les mêmes métadonnées pour désactiver les pistes absentes.

**Tech Stack:** Python 3.12, audio-separator 0.47.0, PySide6, PyInstaller, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-24-model-selection-design.md`

## Global Constraints

- Travailler uniquement dans le dépôt et utiliser `.venv`, `models/`, `.cache/`.
- Aucun push ; un commit local par étape terminée ; hooks obligatoires.
- Ne pas inventer URL, score SDR, taille, SHA-256 ou licence.
- Préserver le blocage des releases publiques aux licences non vérifiées.

---

### Task 1: Catalogue et manifeste

**Files:** `separateur_de_stems/core/models.py`, `models/manifest.json`, `MODELS.md`, `DECISIONS.md`, `tests/packaging/test_manifest.py`.

**Interfaces:** `STEM_TO_MODEL` expose les cinq modèles uniques ; `validate_model_bundle` valide les actifs locaux.

- [x] Tester le nouveau modèle instrumental et les fichiers requis par piste.
- [x] Vérifier que les nouveaux tests échouent.
- [x] Inventorier les actifs déjà présents et relever URL/tailles/hashes vérifiables ; compléter le manifeste et les décisions SDR.
- [x] Exécuter les tests du manifeste et du catalogue ; commiter `feat(models): select best SDR models and inventory assets`.

### Task 2: Téléchargement vérifié et reprenable

**Files:** `scripts/fetch_models.py`, `tests/test_fetch_models.py`, `separateur_de_stems/core/bundle_manifest.py`.

**Interfaces:** `fetch_models(model_dir: Path) -> None` vérifie le manifeste avant de télécharger.

- [x] Écrire les tests serveur HTTP local : cache valide, reprise 206 conforme, Range ignoré, SHA incorrect, fichier absent, URL interdite.
- [x] Confirmer les échecs initiaux, puis coder téléchargement par blocs et remplacement atomique.
- [x] Exécuter tests du script et du manifeste ; commiter `feat(models): add verified resumable model fetcher`.

### Task 3: Disponibilité UI et correspondance moteur

**Files:** `separateur_de_stems/ui/main_window.py`, `separateur_de_stems/core/engine.py`, `tests/ui/test_main_window.py`, `tests/core/test_engine.py`.

**Interfaces:** `missing_assets_by_stem(model_dir)` retourne les actifs absents pour chaque piste ; aucune inférence sur les pistes indisponibles.

- [x] Écrire les tests par piste sur signal synthétique et les tests Qt de désactivation/explication.
- [x] Confirmer les échecs, intégrer la sélection manifestée dans le moteur et le rafraîchissement UI.
- [x] Exécuter tests UI/core et commit `feat(ui): disable stems missing required model assets`.

### Task 4: Build personnel et limites d'artefacts

**Files:** `.github/workflows/build-macos.yml`, `separateur_de_stems/core/packaging.py`, `scripts/validate_release.py`, `README.md`, `tests/packaging/test_workflow.py`.

**Interfaces:** gate personnel valide les actifs sans exiger licence publique ; gate tag reste strict.

- [x] Écrire tests workflow/gates vérifiant ordre téléchargement-build et blocage de tag.
- [x] Implémenter fetch pré-build, mesure/limite archive et documentation des tailles réelles.
- [x] Exécuter tests packaging, commit `ci: fetch models for personal macOS builds`.

### Task 5: Validation et suivi

**Files:** `PLAN.md`, `PROGRESS.md`, et fichiers requis par échecs vérifiés.

- [x] Tester suite complète offscreen, E2E lent sur signal synthétique, traductions.
- [x] Passer les hooks pre-commit, semgrep et gitleaks.
- [x] Contrôler le diff, les fichiers ignorés, les licences non vérifiées et la CI macOS non exécutée localement.
- [x] Mettre à jour PLAN/PROGRESS avec les preuves exactes et commiter `docs: record model integration status`.
