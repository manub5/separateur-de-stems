# Séparateur de pistes (Stem Separator)

Séparateur de pistes audio pour bureau, construit sur
[`audio-separator`](https://github.com/nomadkaraoke/python-audio-separator) et
les modèles UVR (BS-RoFormer, Mel-Band RoFormer, MDX, Demucs v4). Interface
PySide6, identique sous Linux et macOS.

- [Français](#français)
- [English](#english)

---

## Français

### Présentation

L'application sépare un fichier audio en pistes individuelles (voix, batterie,
basse, guitare, piano, instrumental/le reste). Elle s'appuie **uniquement** sur
des modèles déjà éprouvés fournis par `audio-separator` : aucun modèle n'est
entraîné, aucun algorithme de séparation n'est réimplémenté. Le meilleur modèle
disponible par type de piste est choisi automatiquement à partir de son score
SDR (voir `MODELS.md`).

Formats d'entrée : WAV, FLAC, MP3, AIFF, M4A.
Sorties par piste : WAV 24 bits et MP3 320 kb/s.

### Prérequis

- **Python 3.12** (version supportée par toutes les dépendances).
- **ffmpeg** pour le développement et l'usage CLI.
- GPU CUDA optionnel sous Linux (accélération détectée automatiquement).

### Installation (développement)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
# Dépendances de test uniquement :
pip install -e ".[dev]"
```

> Sous Linux, si l'installation de `diffq` échoue (en-têtes Python absents),
> utiliser le contournement `diffq-fixed` documenté dans `DECISIONS.md`
> (D-002).

### Utilisation — ligne de commande

```bash
# Lister les meilleurs modèles par piste
separateur-de-stems --list-models

# Séparer un fichier (voix + instrumental par défaut)
separateur-de-stems morceau.flac

# Choisir les pistes et le dossier de sortie
separateur-de-stems morceau.wav --stems vocals,drums,bass --output-dir sortie

# Export WAV uniquement (sans MP3)
separateur-de-stems morceau.mp3 --no-mp3
```

### Utilisation — interface graphique

```bash
separateur-de-stems-ui
# Optionnel : ouvrir un fichier au lancement
separateur-de-stems-ui --file morceau.flac
```

Glisser-déposer un fichier dans la fenêtre ou utiliser le bouton « Ouvrir »,
cocher les pistes souhaitées, choisir le dossier de sortie, puis lancer la
séparation. Le calcul tourne dans un thread séparé : l'interface ne gèle jamais
et une annulation est toujours possible.

### Traductions

L'interface est bilingue français/anglais (choix dans les réglages, mémorisé).
Les catalogues Qt sont générés à partir des sources `ui/` :

```bash
# (Re)générer le catalogue .ts et compiler le .qm
python scripts/build_translations.py

# Vérifier que le .qm committé est à jour (sans écrire)
python scripts/build_translations.py --check
```

### Compilation

**Linux (PyInstaller) :**

```bash
packaging/build_linux.sh
# Le binaire est produit dans dist/StemSeparator/StemSeparator
```

Sous Linux, ffmpeg est détecté dans le `PATH` ; il est intégré au bundle par la
spécification PyInstaller. Dans l'application figée, le ffmpeg embarqué est
exposé automatiquement : son dossier est placé en tête du `PATH` et pydub est
configuré pour l'utiliser, de sorte que `audio-separator` (qui appelle
`ffmpeg -version`) et l'export MP3 fonctionnent **sans ffmpeg système**.

**macOS (Apple Silicon) :**

La compilation macOS passe par GitHub Actions (`.github/workflows/build-macos.yml`,
runner `macos-14` arm64). Le workflow installe les dépendances (torch CPU/MPS,
sans pile CUDA), vérifie les traductions, teste en mode sans écran, construit le
`.app` avec PyInstaller, le teste (`--help`), puis le compresse en
`StemSeparator-macos.zip` publié comme artefact. Si l'archive dépasse la limite
de taille des artefacts GitHub, elle peut être publiée comme ressource de
*release* (voir `DECISIONS.md`, D-011).

### Premier lancement sous macOS (application non signée)

L'application est **non signée** (pas de signature ni de notarisation Apple).
Au premier double-clic, macOS peut afficher un message de blocage. Procédure :

1. Double-cliquer sur `StemSeparator.app` → message de blocage de macOS.
2. Ouvrir **Réglages Système > Confidentialité et sécurité**.
3. Cliquer sur **« Ouvrir quand même »**.
4. Saisir le mot de passe administrateur.

L'application s'ouvre ensuite normalement. Les modèles ne sont **pas** embarqués
dans le bundle : ils sont téléchargés/cachés au premier usage.

### Crédits et licence

- Séparation : [`audio-separator`](https://github.com/nomadkaraoke/python-audio-separator)
  et les modèles UVR (Ultimate Vocal Remover).
- Interface : [PySide6](https://www.qt.io/qt-for-python) (Qt).
- Détails des modèles, scores SDR, tailles et licences : voir `MODELS.md`.

---

## English

### Overview

This desktop app splits an audio file into individual stems (vocals, drums,
bass, guitar, piano, instrumental/other). It relies **only** on proven models
provided by `audio-separator`: no model is trained and no separation algorithm
is reimplemented. The best available model per stem type is chosen
automatically from its SDR score (see `MODELS.md`).

Input formats: WAV, FLAC, MP3, AIFF, M4A.
Per-stem outputs: 24-bit WAV and 320 kb/s MP3.

### Requirements

- **Python 3.12** (supported by every dependency).
- **ffmpeg** for development and CLI use.
- Optional CUDA GPU on Linux (acceleration is detected automatically).

### Installation (development)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
# Test dependencies only:
pip install -e ".[dev]"
```

> On Linux, if installing `diffq` fails (missing Python headers), use the
> `diffq-fixed` workaround documented in `DECISIONS.md` (D-002).

### Command-line usage

```bash
# List the best models per stem
separateur-de-stems --list-models

# Separate a file (vocals + instrumental by default)
separateur-de-stems track.flac

# Choose stems and output directory
separateur-de-stems track.wav --stems vocals,drums,bass --output-dir out

# WAV only (skip MP3)
separateur-de-stems track.mp3 --no-mp3
```

### Graphical interface usage

```bash
separateur-de-stems-ui
# Optional: open a file at launch
separateur-de-stems-ui --file track.flac
```

Drag and drop a file onto the window (or use the "Open" button), tick the
desired stems, pick the output directory, then start the separation. Processing
runs in a separate thread: the interface never freezes and cancellation is
always available.

### Translations

The interface is bilingual French/English (selected in the settings and
remembered across launches). The Qt catalogs are generated from the `ui/`
sources:

```bash
# (Re)generate the .ts catalog and compile the .qm
python scripts/build_translations.py

# Check that the committed .qm is up to date (without writing)
python scripts/build_translations.py --check
```

### Building

**Linux (PyInstaller):**

```bash
packaging/build_linux.sh
# The binary is produced at dist/StemSeparator/StemSeparator
```

On Linux, ffmpeg is detected on the `PATH`; it is bundled by the PyInstaller
spec. In the frozen app the bundled ffmpeg is exposed automatically: its
directory is prepended to `PATH` and pydub is pointed at it, so
`audio-separator` (which calls `ffmpeg -version`) and the MP3 export both work
**without a system ffmpeg**.

**macOS (Apple Silicon):**

The macOS build runs on GitHub Actions
(`.github/workflows/build-macos.yml`, `macos-14` arm64 runner). The workflow
installs the dependencies (CPU/MPS torch, no CUDA stack), verifies the
translations, runs the headless test suite, builds the `.app` with PyInstaller,
smoke-tests it (`--help`), then zips it as `StemSeparator-macos.zip` published
as an artifact. If the archive exceeds GitHub's artifact size limit, it can be
published as a release asset instead (see `DECISIONS.md`, D-011).

### First launch on macOS (unsigned app)

The app is **unsigned** (no Apple signature or notarization). On the first
double-click, macOS may show a blocking message. Procedure:

1. Double-click `StemSeparator.app` → macOS blocking message.
2. Open **System Settings > Privacy & Security**.
3. Click **"Open Anyway"**.
4. Enter the administrator password.

The app then opens normally. Models are **not** bundled: they are
downloaded/cached on first use.

### Credits and license

- Separation: [`audio-separator`](https://github.com/nomadkaraoke/python-audio-separator)
  and the UVR (Ultimate Vocal Remover) models.
- Interface: [PySide6](https://www.qt.io/qt-for-python) (Qt).
- Model details, SDR scores, sizes and licenses: see `MODELS.md`.
