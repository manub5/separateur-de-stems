# Questions ouvertes

- Q-001 : `htdemucs_6s` n'a pas de score SDR pour guitar/piano. Faut-il
  chercher un modèle spécialisé hors catalogue UVR pour ces pistes ?
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
- Q-006 : vérifier les licences de redistribution des binaires macOS ffmpeg et
  ffprobe ainsi que leur source, version, architecture, SHA-256 et politique de
  dépendances dans
  `packaging/redistributed-binaries.json`, puis générer sur macOS arm64 un lock
  transitif avec hashes. L'upload d'un tag reste bloqué avant ces validations.
- Q-007 : valider sur un runner macOS arm64 MPS/CoreML, `renamex_np` et le
  fonctionnement réel du `.app` final ; ces chemins restent non vérifiés sous
  Linux.
