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

- Instruction « Modèles » (2026-09-24) : sélection SDR par piste terminée
  (voix, instrumental, batterie, basse, guitare/piano), téléchargeur vérifié
  et reprenable (`scripts/fetch_models.py`), désactivation des pistes dont un
  actif manque dans l'UI, et intégration du build macOS terminée : le workflow
  télécharge et vérifie les modèles avant PyInstaller
  (`Fetch and verify selected models`), puis mesure et plafonne la taille de
  l'archive (`scripts/check_artifact_size.py`, plafond conservateur 2 Gio)
  avant tout upload. `validate_build_inputs` accepte désormais une licence
  modèle « À vérifier » pour un build personnel (`require_distributable`
  paramétrable) ; le gate de release taggée reste strict et exige en plus
  `validate_model_bundle(..., require_distributable=True)`.
- Q-006, préparation implémentée : provenance des exécutables Homebrew relevée
  sur macOS, dylib copiées/relocalisées dans le bundle et inventoriées avec
  taille, SHA-256 et licence réelle. Le parcours Mach-O est testé sous Linux
  par simulation et validé sur le runner macOS ; le statut GPL maintient le
  gate public fermé.
- Build personnel macOS arm64 validé par le run GitHub Actions `36242245499` :
  471 tests, PyInstaller, relocation Homebrew, smoke du `.app` et de ffmpeg avec
  `PATH` vide, fermeture Mach-O, checksum et upload ont réussi. L'archive
  `StemSeparator-macos.zip` fait 1 930 531 335 octets (1,798 Gio), sous le
  plafond de 2 Gio, avec SHA-256
  `78228f59bd9b05e469ddcb6e7862d39cb6fbe323aed5dc9f9f50ea3dc3c68fcf`.

## À faire

- Tester une séparation réelle avec MPS/CoreML et l'ouverture graphique du
  `.app` non signé sur un Mac Apple Silicon macOS arm64 distinct du runner.

## Bloqué

- Release publique bloquée intentionnellement : licences des poids à vérifier,
  obligations GPL des binaires/dylib Homebrew non traitées et lock transitif
  macOS arm64 hashé absent. L'inférence MPS/CoreML et l'expérience de premier
  lancement du `.app` non signé restent à valider sur un Mac cible.
