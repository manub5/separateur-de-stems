# Plan

- [x] Créer les fichiers de suivi, la structure du projet, l'environnement virtuel et installer les dépendances avec le contournement `diffq-fixed` documenté.
- [x] Créer le squelette `core` et les tests unitaires de nommage et d'export.
- [x] Implémenter `models.py`, récupérer les modèles, les classer par SDR et mettre à jour `MODELS.md`.
- [x] Implémenter `engine.py`, une CLI minimale et un test de bout en bout synthétique.
- [x] Gérer le choix des pistes et des modèles multiples, ainsi que les sorties WAV 24 bits et MP3.
- [x] Créer l'interface PySide6 avec worker `QThread`, sous-processus annulable et glisser-déposer.
- [x] Ajouter les traductions français/anglais et la persistance des préférences.
- [x] Tester l'empaquetage Linux avec PyInstaller et préparer le workflow macOS différé.
- [x] Task 1 — rendre le cycle d'exécution UI immuable, non bloquant et sûr.
- [x] Task 2 — isoler le pipeline, déplacer les exports hors GUI et confiner le nettoyage.
- [x] Task 3 — imposer les actifs hors ligne et les gates de publication reproductible.
- [x] Task 4 — aligner documentation, licences inconnues et état de publication bloqué.
- [x] Task 5 — exécuter le gate qualité complet ; la validation macOS arm64 et le build distribuable restent conditionnés aux actifs et licences manquants.
- [x] Revue finale — migrer le manifeste modèles vers un inventaire hashé exhaustif et refuser les poids Demucs non inventoriés.
- [x] Revue finale — faire échouer explicitement la résolution des modèles d'un bundle frozen incomplet.
- [x] Revue finale — lier le manifeste ffmpeg/ffprobe aux binaires réels (hash, version, architecture et dépendances injectables).
- [x] Revue finale — placer les gates avant archivage, valider aussi les binaires du bundle et vérifier le checksum de l'archive.
- [x] Revue finale — aligner les documents sur le seul état versionné, exécuter tous les contrôles puis produire un commit unique.
- [x] Sélectionner les meilleurs modèles SDR pour les six pistes et inventorier tous leurs actifs.
- [x] Ajouter le téléchargement vérifié et reprenable dans `models/`.
- [x] Griser dans l'interface les pistes dont les modèles manquent et tester chaque piste.
- [x] Intégrer le téléchargement au workflow macOS personnel et mesurer l'artefact.
- [x] Préparer ffmpeg/ffprobe Homebrew GPL sur le runner et enregistrer version,
  source et SHA-256 réels pour l'artefact personnel.
- [x] Copier/relocaliser les dylib Homebrew et les inclure dans le manifeste du
  `.app` ; garder la release publique bloquée (Q-006).
- [x] Valider le build personnel macOS arm64, ses smokes hors `PATH`, la fermeture
  Mach-O et l'archive de 1 930 531 335 octets ; l'inférence MPS/CoreML réelle
  reste à tester sur un Mac cible (Q-007).
