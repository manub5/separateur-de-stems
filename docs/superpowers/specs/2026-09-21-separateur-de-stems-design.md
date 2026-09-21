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

- Langage : Python 3.12 (3.12.3).
- Moteur : `audio-separator` (repo canonique `nomadkaraoke/python-audio-separator`),
  version 0.47.0, installé et vérifié localement dans `.venv/`.
  - API confirmée : `from audio_separator.separator import Separator`
  - `Separator.__init__` accepte notamment `model_file_dir`, `output_dir`,
    `output_format` (défaut `"WAV"`), `output_bitrate`, `sample_rate`,
    `chunk_duration`, `info_only` (défaut `False`).
  - `load_model(model_filename=...)` (str ou list) / `separate(path)` →
    `list[str]` des fichiers réellement écrits. `separate` accepte
    `custom_output_names={stem: nom}` (clés comparées en minuscules).
  - **Il n'existe PAS de `list_models()`**. Le catalogue s'obtient via
    `Separator(info_only=True).get_simplified_model_list(filter_sort_by=stem)`
    → dict `{filename: {"Name", "Type", "Stems", "SDR"}}`, filtré et trié par
    SDR décroissant pour le stem demandé. `list_supported_model_files()` donne
    la structure brute groupée par architecture (`list_format=json` = ce dict).
  - Erreurs (ré-exportées depuis `audio_separator.separator`) :
    `BatchSeparationError` (`.successful_files`, `.failures`),
    `InvalidAudioDataError`, `AudioExportError` (`.path`, `.backend`).
  - Accélération auto : CUDA (`[gpu]`), MPS/CoreML Apple Silicon (`[cpu]`),
    sinon CPU. Sur macOS arm64 audio-separator exige `torch>=2.13` ; sur Linux
    `torch>=2.3`. Vérifié en local : Python 3.12 + torch 2.14.0+cu130 + CUDA
    (RTX 3060) + onnxruntime-gpu → `--env_info` confirme torch ET onnx CUDA.
  - **Pas d'annulation ni de callback de progression intra-modèle** : l'API
    n'expose aucun `stop_event`/hook. Toute la progression interne passe par
    `tqdm` (console). Conséquence : progression **par étape/modèle** uniquement,
    et l'annulation nécessite de **tuer un sous-processus**.
  - **Hors ligne strict** : `load_model` exige que le filename figure dans le
    catalogue, et `list_supported_model_files()` télécharge
    `download_checks.json` s'il est absent de `model_file_dir`. Un mode 100 %
    hors ligne devra donc embarquer les poids **et** `download_checks.json`
    (et les configs MDXC `*.yaml` / data JSON).
- Installation locale Linux (contournement documenté) : les headers Python
  (`Python.h`) sont absents du système et interdits d'installation (`sudo`/`apt`).
  `diffq` (dep. Linux d'audio-separator) ne compile donc pas. Solution :
  installer `diffq-fixed` (wheel cp312 manylinux, l'alternative déjà utilisée par
  audio-separator sous Windows) puis `pip install audio-separator --no-deps` et
  compléter les dépendances manuellement. Détails dans `DECISIONS.md`.
- Accélération locale : CUDA (RTX 3060) confirmée par `--env_info`.
- Interface : PySide6 (Qt).
- Encodage MP3 : ffmpeg (présent localement ; embarqué pour le `.app` final).

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

- Récupère le catalogue réel via `get_simplified_model_list(filter_sort_by=...)`
  et l'expose en structures typées.
- Table de mapping `STEM → filename` figée à partir du catalogue réel vérifié :

  | Piste | Modèle retenu | SDR | Arch |
  |---|---|---|---|
  | Voix (`vocals`) | `vocals_mel_band_roformer.ckpt` | 12.6 | MDXC |
  | Instrumental | `model_bs_roformer_ep_317_sdr_12.9755.ckpt` | 16.5 | MDXC |
  | Batterie (`drums`) | `htdemucs_ft.yaml` | 10.0 | Demucs |
  | Basse (`bass`) | `hdemucs_mmi.yaml` | 12.2 | Demucs |
  | Guitare (`guitar`) | `htdemucs_6s.yaml` | — (non fourni) | Demucs |
  | Piano (`piano`) | `htdemucs_6s.yaml` | — (non fourni) | Demucs |

  Le mapping est **vérifié au runtime** contre le catalogue réel ; si un modèle
  attendu est absent → `ModelUnavailableError` (pas de crash).
- `select_models(stems: set[str]) -> list[ModelSpec]` : déduit les modèles
  nécessaires des cases cochées. Un modèle multi-pistes peut couvrir plusieurs
  pistes (ex. `htdemucs_6s.yaml` pour guitare + piano ; RoFormer pour
  voix/instrumental).
- Catalogue documenté dans `MODELS.md` (nom, piste(s), SDR, taille, source,
  licence). **Limite connue** : guitare et piano ne sont couverts que par
  `htdemucs_6s` sans score SDR → à signaler dans `QUESTIONS.md`.

### 5.2 `core/engine.py`

- `SeparationEngine` encapsule `Separator`.
- `prepare(models)` : charge les modèles.
- `run(input_path, stems, progress_cb, cancel_event)` :
  - `progress_cb(percent: int, stage: str)` appelé **par étape/modèle**.
  - **Annulation** : l'API n'offre aucun point d'interruption. L'annulation
    repose sur l'exécution de la séparation dans un **sous-processus tuable**
    (`multiprocessing.Process`), surveillé par le parent. `cancel_event` est
    vérifié entre étapes côté parent ; une annulation en cours d'inférence tue
    le sous-processus. (La CLI peut aussi appeler in-process pour un usage
    simple, sans annulation.)
  - Limite assumée : tuer le sous-processus ne permet pas de reprendre à
    mi-modèle ; le fichier partiel est supprimé.
- Single-thread côté inférence (le GPU est déjà saturé par torch).

### 5.3 `core/export.py`

- `Separator` écrit le format de sortie demandé (`output_format="WAV"`).
- WAV 24 bits : contrôle du subtype `PCM_24` via `soundfile` (relecture +
  réécriture si nécessaire).
- MP3 320 kb/s : `output_format="MP3"`, `output_bitrate="320k"` (ffmpeg).
- Les deux formats sont produits par piste.

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
[Main thread]                       [QThread worker]           [sous-processus]
Drop/open ──► "Séparer" ──► SeparationWorker.run()
                              ├─ core.select_models
                              ├─ core.engine.run ────────────► séparation
                              │      (cancel_event)              (tuable)
                              └─ core.export
                              ▼
             signaux: progress(int,str) / finished(list) / error(str)
                              ▼
 ProgressBar ◄── progress       │  Annuler ──► cancel_event.set()
                                            └─► terminate sous-processus
```

- Le worker Qt ne contient **aucune** logique métier : il traduit les callbacks
  `core` en signaux.
- Aucun widget n'est touché depuis le thread worker.
- Pas de QThreadPool parallèle.
- Le sous-processus tuable est la seule façon d'annuler une inférence en cours
  (l'API audio-separator n'expose aucun point d'interruption).

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

1. `PLAN.md`, `DECISIONS.md`, `PROGRESS.md`, `.gitignore`, structure, venv +
   dépendances (contournement `diffq-fixed` documenté).
2. Squelette `core` + tests unitaires (`naming`, `export`).
3. `models.py` : récupération réelle des modèles, classement SDR, `MODELS.md`.
4. `engine.py` + CLI minimale + test E2E synthétique.
5. Choix des pistes / modèles multiples, sorties WAV24 + MP3.
6. UI PySide6 + worker QThread + sous-processus tuable (annulation) + drag&drop.
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
