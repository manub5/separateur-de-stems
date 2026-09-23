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
- Phase 2 / Plan C, état antérieur, supersédé par le durcissement : un prototype
  PyInstaller Linux et un workflow macOS avaient été préparés avec modèles hors
  bundle. Cet état ne validait aucun artefact distribuable ni son exécution sur
  macOS arm64.
- Durcissement Tasks 1 à 3 terminé : état d'exécution UI immuable, annulation
  et fermeture asynchrones, pipeline/export hors GUI avec publication atomique,
  espace privé et nettoyage confiné, puis gates stricts d'empaquetage hors
  ligne et manifeste de modèles.
- Task 4 terminée : README bilingue, notices, questions et état de publication
  alignés sur les comportements durcis et les blockers vérifiés.
- Task 5 terminée : 427 tests rapides et le gate lent exécutés, traductions à
  jour, hooks pre-commit/semgrep/gitleaks passés et revue finale approuvée. Le
  build et son smoke restent bloqués avant artefact par les gates stricts.
- Revue finale terminée : inventaire hashé exhaustif des actifs, résolution
  frozen fail-closed et validation des vrais ffmpeg/ffprobe avant artefact
  (hash, version, architecture et dépendances macOS).

## À faire

- Valider le build et les smokes sur macOS arm64 après résolution des blockers.

## Bloqué

- Build distribuable bloqué intentionnellement : poids/configurations/checksums
  et licences des modèles incomplets, dont les poids Demucs `.th` pas tous
  inventoriés ; métadonnées ffmpeg/ffprobe inconnues et lock transitif macOS
  arm64 hashé absent. MPS/CoreML, `renamex_np` et le `.app` final attendent une
  validation sur runner macOS arm64.
