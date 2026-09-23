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

- Durcissement de la livraison hors ligne : gate strict et smoke bundle
  implémentés ; validation macOS arm64 réelle en attente du workflow.

## À faire

- Compléter et valider légalement les actifs de `models/manifest.json`, puis
  exécuter le workflow macOS arm64. Signature/notarisation Apple et accélération
  MPS/CoreML restent ensuite à revérifier.

## Bloqué

- Build distribuable bloqué intentionnellement : poids/configurations/checksums
  et licences des modèles incomplets.
