# Séparateur de pistes (Stem Separator)

Application de bureau PySide6 fondée sur
[`audio-separator`](https://github.com/nomadkaraoke/python-audio-separator) et
des modèles UVR éprouvés. Aucun modèle n'est entraîné et aucun algorithme de
séparation n'est réimplémenté dans ce projet.

- [Français](#français)
- [English](#english)

---

## Français

### Fonctionnement

L'application accepte WAV, FLAC, MP3, AIFF et M4A et produit, pour chaque piste
demandée, un WAV 24 bits et un MP3 320 kb/s. Les pistes proposées sont voix,
batterie, basse, guitare, piano et instrumental/reste. La sélection des modèles
est décrite dans `MODELS.md`.

Une exécution capture une configuration immuable. L'entrée, la sortie et les
réglages restent verrouillés jusqu'au signal natif `QThread.finished`.
L'annulation et la fermeture sont asynchrones : elles demandent l'arrêt sans
bloquer la boucle Qt, puis attendent la fin native du thread.

La séparation et les exports WAV/MP3 s'exécutent hors de l'interface. Chaque
lot utilise un espace de travail privé, convertit le WAV par blocs bornés,
permet d'annuler ffmpeg et vérifie que tous les résultats existent. Un lot
complet est publié atomiquement dans un nouveau dossier de morceau ; un dossier
de morceau existant n'est jamais remplacé. L'échec ou l'annulation ne nettoie
que l'espace privé de l'exécution.

### Prérequis et développement

- Python `>=3.12,<3.13`, plage déclarée dans `pyproject.toml`.
- ffmpeg et ffprobe accessibles pour l'usage en développement.
- Un répertoire de modèles local est recommandé pour maîtriser les actifs
  utilisés.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

separateur-de-stems --list-models
separateur-de-stems morceau.flac --stems vocals,drums --output-dir sortie
separateur-de-stems morceau.mp3 --no-mp3

separateur-de-stems-ui
separateur-de-stems-ui --file morceau.flac
```

Sous Linux, l'interface utilise XCB/XWayland par défaut pour éviter des défauts
de rafraîchissement observés sous KDE Wayland avec NVIDIA. Vous pouvez choisir
explicitement un autre backend avec `QT_QPA_PLATFORM` ; une valeur déjà définie
est toujours conservée (par exemple `offscreen` pour les tests).

En développement, les modèles résident dans `models/` ou dans le répertoire
explicitement choisi dans les réglages. Si un actif manque,
`audio-separator` peut télécharger et mettre en cache des fichiers selon son
propre comportement. Le développement n'offre donc pas une garantie hors ligne.

### Traductions et tests

```bash
python scripts/build_translations.py
python scripts/build_translations.py --check
QT_QPA_PLATFORM=offscreen python -m pytest -q
```

### Builds et publication hors ligne

Le build de développement Linux se lance avec `packaging/build_linux.sh`. Le
workflow macOS est `.github/workflows/build-macos.yml`.

**PUBLICATION BLOQUÉE.** Le bundle de publication vise un fonctionnement hors ligne.
Son gate vérifie les actifs déclarés, leurs configurations,
`download_checks.json`, ffmpeg et ffprobe avant le build. Le manifeste est
incomplet : le manifeste versionné n'inventorie aucun poids Demucs `.th`, et
d'autres poids, configurations, tailles, SHA-256, sources ou
licences manquent. Les licences, sources et versions des binaires restent
inconnues dans `packaging/redistributed-binaries.json`. Enfin,
`requirements/macos-arm64.lock` n'est qu'un inventaire direct épinglé : le vrai
`requirements/macos-arm64-transitive.lock` avec hashes n'existe pas encore.
Aucun artefact public de tag n'est donc autorisé.

Le build de développement et le build de publication diffèrent : le premier
peut utiliser les actifs locaux et les outils du `PATH`; le second doit franchir
toutes les validations du manifeste et embarquer modèles, ffmpeg et ffprobe.

L'accélération macOS MPS/CoreML est déléguée à `audio-separator`.
MPS/CoreML, `renamex_np` et le `.app` final restent non vérifiés jusqu'à
l'exécution du workflow sur macOS arm64. L'application prévue est non signée ;
au premier lancement, utiliser **Réglages Système > Confidentialité et sécurité
> Ouvrir quand même**, puis saisir le mot de passe administrateur.

Les attributions vérifiées et les éléments en attente figurent dans
`THIRD_PARTY_NOTICES.md`.

---

## English

### Behavior

The application accepts WAV, FLAC, MP3, AIFF, and M4A and produces a 24-bit WAV
and a 320 kb/s MP3 for each requested stem. Available stems are vocals, drums,
bass, guitar, piano, and instrumental/other. Model selection is documented in
`MODELS.md`.

Each run captures immutable configuration. Input, output, and settings controls
remain locked until native `QThread.finished`. Cancellation and closing are
asynchronous: they request shutdown without blocking the Qt event loop and
wait for native thread completion.

Separation and WAV/MP3 exports run outside the GUI. Each batch uses a private
workspace, performs bounded-block WAV conversion, supports cancellable ffmpeg,
and verifies every result. A complete batch is published atomically to a new
song directory; an existing song directory is never replaced. Failure or
cancellation cleans only that run's private workspace.

### Requirements and development

- Python `>=3.12,<3.13`, as declared by `pyproject.toml`.
- ffmpeg and ffprobe available for development use.
- A local model directory is recommended to control the assets being used.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

separateur-de-stems --list-models
separateur-de-stems track.flac --stems vocals,drums --output-dir out
separateur-de-stems track.mp3 --no-mp3

separateur-de-stems-ui
separateur-de-stems-ui --file track.flac
```

On Linux, the GUI defaults to XCB/XWayland to avoid redraw artifacts observed
on KDE Wayland with NVIDIA. Set `QT_QPA_PLATFORM` explicitly to select another
backend; an existing value is always preserved (for example, `offscreen` for
tests).

In development, models live in `models/` or in the directory explicitly chosen
in settings. If an asset is missing, `audio-separator` may download and cache
files according to its own behavior. Development therefore has no offline
guarantee.

### Translations and tests

```bash
python scripts/build_translations.py
python scripts/build_translations.py --check
QT_QPA_PLATFORM=offscreen python -m pytest -q
```

### Builds and offline publication

Run the Linux development build with `packaging/build_linux.sh`. The macOS
workflow is `.github/workflows/build-macos.yml`.

**PUBLIC RELEASE BLOCKED.** The release bundle targets offline operation. Its
gate verifies declared assets, their configs, `download_checks.json`, ffmpeg,
and ffprobe before building. The manifest is incomplete: required Demucs
weights in `.th` files are not inventoried in the versioned manifest, and other
payloads, configs, sizes, SHA-256 hashes, sources, or licences are missing. The
licences, sources, and versions of redistributed binaries remain unknown in
`packaging/redistributed-binaries.json`. Finally,
`requirements/macos-arm64.lock` is only a pinned direct inventory; a true
hashed `requirements/macos-arm64-transitive.lock` does not exist yet. No public
tag artifact is therefore permitted.

Development and release builds differ: development may use local assets and
tools from `PATH`; release must pass every manifest gate and bundle the models,
ffmpeg, and ffprobe.

macOS MPS/CoreML acceleration is delegated to `audio-separator`.
MPS/CoreML, `renamex_np`, and the final `.app` remain unverified until the
workflow runs on macOS arm64. The intended app is unsigned; on first launch use
**System Settings > Privacy & Security > Open Anyway**, then enter the
administrator password.

Verified attributions and pending items are listed in
`THIRD_PARTY_NOTICES.md`.
