# Spec — Séparateur de pistes, Plan C (packaging)

Date : 2026-09-22
Statut : validé (brainstorming)
Précède : `2026-09-22-phase2-ui-design.md`, Plans A (UI) et B (i18n)

## 1. Objectif

Livrer une application distribuable : un exécutable local Linux (testé) et un
`.app` macOS Apple Silicon construit par GitHub Actions, emballant toutes les
dépendances sauf les modèles, accompagné d'un README bilingue.

## 2. Décisions de cadrage

| Sujet | Décision |
|---|---|
| Contenu du bundle | PyInstaller + PySide6 + audio-separator + torch + onnxruntime + soundfile + ffmpeg ; **modèles hors bundle** (téléchargés dans le dossier utilisateur) |
| Mode PyInstaller | `onedir` (Linux comme macOS) ; `.app` = dossier |
| ffmpeg | Embarqué (`--add-binary`), résolu via `ui.paths.ffmpeg_dir()` |
| Test local Linux | Build `onedir` + smoke `--help` (pas d'inférence) |
| Poids modèle | Reste téléchargé (Q-002/Q-003) ; les **données** audio-separator (JSON/YAML) sont embarquées |
| Artefact CI | `upload-artifact` du `.zip` du `.app` ; repli GitHub Release documenté si trop gros |
| Signature | Non signée ; procédure « Ouvrir quand même » documentée FR/EN |
| README | Un seul `README.md` bilingue |

## 3. Structure

```
packaging/
├── stem-separator.spec       # spec PyInstaller (Linux + macOS)
├── runtime_hook.py           # multiprocessing.freeze_support, env torch
├── build_linux.sh            # build local reproductible + smoke
└── (dist/ et build/ générés, ignorés)
.github/workflows/
└── build-macos.yml           # CI macOS arm64
README.md                     # bilingue FR/EN
```

Nom du produit : `StemSeparator`.

## 4. Spec PyInstaller

- Entrée : `separateur_de_stems/ui/app.py` ; `--windowed` (pas de console) ;
  `runtime_hook_path` = `packaging/runtime_hook.py`.
- `collect_data_files("audio_separator")` et
  `collect_data_files("separateur_de_stems")` (pour `ui/i18n/*.qm`/`*.ts`).
- `collect_submodules("torch")`, `collect_dynamic_libs("torch"/"onnxruntime")`,
  `hiddenimports` pour les architectures audio-separator.
- Exclusions : `tkinter`, `matplotlib`, `pytest`, `PySide6.QtWebEngine*`,
  `PySide6.Qt3D*`, `PySide6.QtCharts`.
- ffmpeg : `binaries=[(ffmpeg_path, "ffmpeg")]` (+ `ffprobe` si disponible).
- macOS : bloc `BUNDLE` (`StemSeparator.app`, bundle identifier, `NSHighResolutionCapable`).
- Linux : `COLLECT` produit `dist/StemSeparator/`.

## 5. ffmpeg embarqué

- `ui/paths.py::ffmpeg_dir()` existe déjà (résout `sys._MEIPASS`/bundle).
- **Petit ajout `core/export.py`** : avant `subprocess.run`, résoudre le chemin
  de ffmpeg via `ffmpeg_dir()` si défini (sinon `"ffmpeg"` du PATH). Testable
  sans bundle (monkeypatch de `ffmpeg_dir`).
- CI macOS : `brew install ffmpeg` puis le spec copie le binaire dans le bundle.
- Linux local : le spec copie le ffmpeg système pour le test.

## 6. Workflow macOS

`.github/workflows/build-macos.yml`, runner `macos-14` (arm64) :
checkout → Python 3.12 → installation des dépendances + outillage →
`pytest -m "not slow"` → `scripts/build_translations.py --check` →
`pyinstaller packaging/stem-separator.spec` → smoke `--help` → zip du `.app` →
`upload-artifact`. Déclencheurs `workflow_dispatch` + tags `v*`.

## 7. README bilingue

`README.md` : bandeau de langue, puis **FR** et **EN** — présentation,
prérequis (Python 3.12, ffmpeg en dev), installation, CLI, UI, traductions,
build PyInstaller, **macOS non signé** (Réglages Système > Confidentialité et
sécurité > « Ouvrir quand même » > mot de passe), crédits UVR.

## 8. Tests

- `tests/packaging/` : présence et validité du spec ; YAML du workflow valide ;
  `ffmpeg_dir` frozen (mock) ; cohérence du runtime hook.
- Smoke binaire Linux : `packaging/build_linux.sh` puis
  `dist/StemSeparator/StemSeparator --help` → code 0. Marquable `slow`.
- macOS : non testable localement ; le workflow fait office de test.
- `core/export.py` : test que le chemin ffmpeg embarqué est utilisé si défini.

## 9. Hors périmètre

- Modèles embarqués (Q-002/Q-003).
- Signature/notarisation Apple.
- CI Linux dédiée et publication GitHub Release automatique (repli documenté).
- Optimisations de taille avancées (UPX, etc.).
