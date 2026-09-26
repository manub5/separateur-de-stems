# Questions ouvertes

- Q-001 — Résolue techniquement : `htdemucs_6s.yaml` n'a pas de score SDR
  publié pour guitar/piano, mais c'est le SEUL modèle de tout le catalogue
  `audio-separator --list_models` (0.47.0) qui propose ces deux pistes
  (`--list_filter=guitar` et `--list_filter=piano` ne retournent que lui).
  La pile technique imposée (AGENTS.md) limite les modèles à ceux exposés par
  `audio-separator` ; il n'y a donc aucune alternative disponible dans cette
  bibliothèque pour ces deux pistes.
- Q-002 — Résolue techniquement : la publication exige des modèles intégrés et
  validés par manifeste ; aucun téléchargement au premier usage n'est prévu.
  La publication reste bloquée tant que les actifs et licences manquent.
- Q-003 — Résolue techniquement : le gate d'empaquetage exige les poids,
  `download_checks.json` et les configurations. Le manifeste versionné conserve
  des métadonnées inconnues, donc aucun bundle de publication ne peut être produit.
- Q-004 : les licences des modèles retenus restent « À vérifier » dans
  MODELS.md. Vérifier leur compatibilité avec une diffusion publique de
  l'application avant toute distribution.
- Q-005 : compléter `models/manifest.json` avec les fichiers réellement
  retenus, leurs configurations, tailles, SHA-256, sources et licences vérifiées.
  Le build distribuable est volontairement bloqué jusque-là.
- Q-006 : Homebrew annonce ffmpeg GPL-3.0-or-later et dépend explicitement de
  x264/x265 (GPL-2.0-or-later). Source, version et SHA-256 des exécutables et
  dylib recopiées sont relevés sur le runner macOS ; aucun hash macOS n'est
  inventé depuis Linux. Un artefact personnel reste possible, mais AUCUNE
  release publique (tag ni page Releases) tant que les obligations GPL,
  notices/sources et licences des dépendances ne sont pas traitées. Le lock
  transitif macOS hashé reste également à produire sur arm64.
- Q-007 : partiellement résolue par le run macOS arm64 `36242245499`. Le `.app`
  est construit, ses dépendances Mach-O sont fermées, son binaire démarre et
  ffmpeg encode avec un `PATH` vide. Il reste à tester sur un Mac cible une
  séparation réelle MPS/CoreML, `renamex_np`, l'interface graphique et le
  premier lancement de l'application non signée.
