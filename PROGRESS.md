# Progression

## Fait

- Spec validé et commité.
- Venv local opérationnel : Python 3.12, torch 2.14.0+cu130, CUDA RTX 3060.
- Phase 1 (CLI) : séparation en ligne de commande, choix des modèles, export
  WAV 24 bits et MP3 320 kb/s, annulation par sous-processus.
- Phase 2 / Plan A (UI) terminé : fenêtre principale (`MainWindow`), worker
  QThread pilote de `SubprocessSeparator`, glisser-déposer (`DropZone`),
  réglages persistés (`QSettings`), dialogue de préférences et test de fumée
  de l'application. Suite de tests complète (211 tests) verte en offscreen.

## En cours

- Rien.

## À faire

- Phase 2 / Plan B : internationalisation (traductions FR/EN, choix mémorisé).
- Phase 2 / Plan C : empaquetage (PyInstaller + workflow macOS Apple Silicon).

## Bloqué

- Rien.
