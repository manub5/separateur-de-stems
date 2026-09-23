# Questions ouvertes

- Q-001 : `htdemucs_6s` n'a pas de score SDR pour guitar/piano. Faut-il
  chercher un modèle spécialisé hors catalogue UVR pour ces pistes ?
- Q-002 : la stratégie de distribution des modèles (CI/GitHub) est différée ;
  tout reste local au PC pour l'instant.
- Q-003 : le mode 100 % hors ligne exige d'embarquer les poids,
  `download_checks.json` et les configurations MDXC. À traiter lors de la phase
  d'empaquetage.
- Q-004 : les licences des modèles retenus restent « À vérifier » dans
  MODELS.md. Vérifier leur compatibilité avec une diffusion publique de
  l'application avant toute distribution.
- Q-005 : compléter `models/manifest.json` avec les fichiers réellement
  retenus, leurs configurations, tailles, SHA-256, sources et licences vérifiées.
  Le build distribuable est volontairement bloqué jusque-là.
- Q-006 : vérifier les licences de redistribution des binaires macOS ffmpeg et
  ffprobe dans `packaging/redistributed-binaries.json`, puis générer sur macOS
  arm64 un lock transitif avec hashes. L'upload d'un tag reste bloqué avant ces
  deux validations.
