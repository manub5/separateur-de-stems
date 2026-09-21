# Spec — Séparateur de pistes (stems)

Date : 2026-09-21
Statut : validé (brainstorming)

## 1. Objectif

Application de bureau qui sépare un fichier audio en pistes (voix, batterie,
basse, guitare, piano, reste), de qualité comparable à iZotope RX / Ableton
Live 12, en s'appuyant uniquement sur des bibliothèques et modèles éprouvés.

- Cible finale : application `.app` native pour iMac Apple Silicon (M1 et +).
- Développement et tests : poste Linux (Kubuntu).
- Premier livrable : pipeline en ligne de commande, testable de bout en bout.

## 2. Contraintes non négociables (rappel AGENTS.md)

- Travail exclusivement dans le dossier du projet.
- Jamais de `sudo`, ni installation système, ni modification de config globale.
- Dépendances Python dans `.venv/` local ; modèles dans `./models/` ; caches
  dans `./.cache/`.
- Git local uniquement, un commit par étape, hooks pre-commit/semgrep/gitleaks
  obligatoires, jamais de `git push`.
- Vérifier toute API dans la doc officielle avant usage ; consigner les
  inconnues dans `QUESTIONS.md`.

## 3. Décisions de cadrage (issues du brainstorming)

| Sujet | Décision |
|---|---|
| Version Python | **3.12** (3.12.3 présent ; audio-separator 0.47.0 exige `>=3.10`, hors 3.14.1) |
| Premier livrable | **Pipeline CLI** d'abord, puis UI |
| Choix des modèles | **1 modèle optimal par piste**, classement SDR, RoFormer privilégiés |
| Concurrence UI | **QThread worker unique + signaux Qt**, annulation coopérative |
| Distribution des modèles | **Tout reste local sur le PC** pour l'instant ; stratégie CI/GitHub différée |
| Classification projet | Architectural (nouveau projet) |

## 4. Pile technique

- Langage : Python 3.12.
- Moteur : `audio-separator` (karaokenerds/python-audio-separator), version 0.47.0.
  - API confirmée : `from audio_separator.separator import Separator`
  - `Separator(model_file_dir=..., output_dir=..., output_format=...)`
  - `load_model(model_filename=...)` / `separate(path)` → liste de chemins
  - Liste des modèles : `Separator(info_only=True).list_models()` ou CLI
    `--list_models --list_format=json`
  - Erreurs : `BatchSeparationError`, `InvalidAudioDataError`, `AudioExportError`
  - Accélération auto : CUDA (`[gpu]`), MPS/CoreML Apple Silicon (`[cpu]`),
    sinon CPU. Sur macOS arm64 audio-separator exige `torch>=2.13` ; sur Linux
    `torch>=2.3`. À surveiller (voir QUESTIONS).
  - Sortie par défaut FLAC ; sortie WAV/MP3 configurable.
  - Progression : **pas de callback intra-modèle** dans l'API publique →
    progression par étape/modèle uniquement.
- Accélération locale : CUDA (RTX 3060) détectée par `--env_info`.
- Interface : PySide6 (Qt).
- Encodage MP3 : ffmpeg (présent localement ; embarqué pour le `.app` final).
- Empaquetage : PyInstaller (à valider à l'étape 8).

## 5. Architecture

```
separateur_de_stems/
├── core/
│   ├── models.py      # catalogue modèles + choix par piste (SDR)
│   ├── engine.py      # wrapper audio-separator (load/separate, annulation)
│   ├── naming.py      # nommage des fichiers de sortie
│   └── export.py      # conversion WAV 24-bit + MP3 320
├── cli.py             # première façade livrable
├── ui/                # PySide6 (étape ultérieure)
├── i18n/              # .ts/.qm FR/EN
└── config.py          # chemins modèles/cache/sortie, préférences
```

Principe directeur : `core/` ne dépend d'**aucune** bibliothèque Qt. `cli.py` et
`ui/` sont deux façades minces sur le même `core/`. Toute la logique métier est
donc testable sans interface.

### 5.1 `core/models.py`

- Récupère la liste réelle des modèles (JSON) et l'expose en structures typées.
- Table de mapping `STEM → modèle` vérifiée au runtime contre la liste réelle ;
  si un modèle attendu est absent → `ModelUnavailableError` (pas de crash).
- `select_models(stems: set[str]) -> list[ModelSpec]` : déduit les modèles
  nécessaires des cases cochées. Un modèle multi-pistes peut couvrir plusieurs
  pistes.
- Catalogue documenté dans `MODELS.md` (nom, piste(s), SDR, taille, source,
  licence).

### 5.2 `core/engine.py`

- `SeparationEngine` encapsule `Separator`.
- `prepare(models)` : charge les modèles.
- `run(input_path, stems, progress_cb, cancel_event)` :
  - `progress_cb(percent: int, stage: str)` appelé **par étape/modèle**.
  - `cancel_event` (`threading.Event`) vérifié **entre** les étapes →
    annulation coopérative.
  - Limite assumée : un modèle en cours ne peut pas être interrompu à mi-calcul.
- Single-thread côté inférence (le GPU est déjà saturé par torch).

### 5.3 `core/export.py`

- WAV 24 bits : conversion via `soundfile` (subtype `PCM_24`).
- MP3 320 kb/s : ffmpeg (`--output_bitrate=320k` natif, ou appel ffmpeg direct).

### 5.4 `core/naming.py`

- Nommage déterministe `<morceau>_<piste>.<ext>`, sanitisation des caractères.
- Collision → suffixe `_1`, `_2`.

### 5.5 `config.py`

- Chemins : `./models/`, `./.cache/`, dossier de sortie par défaut.
- Préférences (langue) : `QSettings` côté UI.

## 6. Flux de données & threading

### CLI (étape 1)

```
fichier → select_models(stems) → engine.run(...) → export WAV24+MP3 → console
```

### UI (étape ultérieure)

```
[Main thread]                          [QThread worker]
Drop/open ──► "Séparer" ──► SeparationWorker.run()
                              ├─ core.select_models
                              ├─ core.engine.run (cancel_event)
                              └─ core.export
                              ▼
             signaux: progress(int,str) / finished(list) / error(str)
                              ▼
 ProgressBar ◄── progress       │  Annuler ──► cancel_event.set()
```

- Le worker Qt ne contient **aucune** logique métier : il traduit les callbacks
  `core` en signaux.
- Aucun widget n'est touché depuis le thread worker.
- Pas de QThreadPool parallèle.

## 7. Gestion des erreurs

Hiérarchie `core` (base `StemSeparatorError`, messages FR/EN affichables) :

- `UnsupportedFormatError` — fichier hors WAV/FLAC/MP3/AIFF/M4A.
- `ModelUnavailableError` — modèle absent / téléchargement impossible.
- `OutputError` — dossier non inscriptible, disque plein, échec ffmpeg.
- `CancelledError` — annulation volontaire (retour propre, pas une erreur UI).

Vérifications **avant** inférence : format lisible, dossier de sortie
inscriptible, espace disque, disponibilité des modèles. Log complet dans
`.cache/`, message lisible à l'écran.

Cas limites identifiés (couverts par les tests) :

- audio sans voix → stem silencieux écrit quand même (pas de filtrage pour
  l'instant).
- fichiers très longs (>1 h) → option avancée `chunk_duration`.
- collision de noms de sortie → suffixes.

## 8. Tests (Linux, avant chaque commit)

- **Unitaires** : `naming`, `export`, `models.select_models` (sans ML).
- **E2E moteur** : signal synthétique court avec le modèle le plus léger.
- **UI headless** : `QT_QPA_PLATFORM=offscreen`, construction de fenêtre +
  signaux du worker, sans inférence.
- **macOS-spécifique** (MPS/CoreML, `.app`) : non testable ici → module isolé,
  skip/xfail, signalé dans `PROGRESS.md`.

## 9. Étapes du plan (chacune testable + un commit)

1. `PLAN.md`, `DECISIONS.md`, `PROGRESS.md`, `.gitignore`, structure, monde
   `.venv` + dépendances.
2. Squelette `core` + tests unitaires (`naming`, `export`).
3. `models.py` : récupération réelle des modèles, classement SDR, `MODELS.md`.
4. `engine.py` + CLI minimale + test E2E synthétique.
5. Choix des pistes / modèles multiples, sorties WAV24 + MP3.
6. UI PySide6 + worker QThread + annulation + drag&drop.
7. Traductions FR/EN + persistance des préférences.
8. Empaquetage Linux (test PyInstaller) + préparation workflow macOS (différé,
   local d'abord).

## 10. Hors périmètre (pour cette itération)

- Entraînement ou modification de modèles.
- Stratégie de distribution GitHub / CI (différée, décision locale).
- Filtrage de stems silencieux par seuil de loudness.
- Optimisations avancées (autocast, torch.compile, fp16).

## 11. Lieux de documentation projet

- `PLAN.md` — étapes courtes et testables.
- `PROGRESS.md` — fait / en cours / bloqué.
- `DECISIONS.md` — choix techniques non triviaux et leurs raisons.
- `MODELS.md` — catalogue des modèles retenus.
- `QUESTIONS.md` — inconnues et décisions en attente.
