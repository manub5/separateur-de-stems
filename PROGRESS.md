# Progression

## Fait

- Spec validé et commité.
- Venv local opérationnel : Python 3.12, torch 2.14.0+cu130, CUDA RTX 3060.
- Phase 1 (CLI) : séparation en ligne de commande, choix des modèles, export
  WAV 24 bits et MP3 320 kb/s, annulation par sous-processus.
- Phase 2 / Plan A (UI) terminé : fenêtre principale (`MainWindow`), worker
  QThread pilote de `SubprocessSeparator`, glisser-déposer (`DropZone`),
  réglages persistés (`QSettings`), dialogue de préférences et test de fumée
  de l'application.
- Phase 2 / Plan B (i18n) terminé : catalogues FR compilés (`.ts`/`.qm`),
  libellés `tr()` extraits, changement de langue à chaud via
  `LanguageChange`/`retranslate_ui` (fenêtre, dialogue de réglages, zone de
  dépôt), langue chargée au démarrage, garde de fraîcheur du catalogue
  (`build(check=True)`). Suite de tests complète (267 tests) verte en offscreen.
- Phase 2 / Plan C (packaging) terminé : empaquetage PyInstaller Linux
  (`onedir`, `packaging/build_linux.sh`, modèles hors bundle, ffmpeg embarqué
  résolu par `core.platform.ffmpeg_executable`, `.qm` committée embarquée) ;
  workflow macOS Apple Silicon (`.github/workflows/build-macos.yml`, runner
  `macos-14`, torch CPU/MPS, actions épinglées par SHA, test offscreen,
  `.app` non signée compressée en artefact) ; README bilingue FR/EN
  (`README.md`) documentant installation, CLI, UI, traductions, builds et
  premier lancement macOS non signé. Suite de tests complète verte en
  offscreen (dont `tests/packaging/test_readme.py`).

## En cours

- Rien.

## À faire

- Rien (Plan C terminé). Suite éventuelle : signature/notarisation Apple,
  accélération MPS/CoreML à revérifier sur une machine Apple Silicon.

## Bloqué

- Rien.
