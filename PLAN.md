# Plan

- [x] Créer les fichiers de suivi, la structure du projet, l'environnement virtuel et installer les dépendances avec le contournement `diffq-fixed` documenté.
- [x] Créer le squelette `core` et les tests unitaires de nommage et d'export.
- [x] Implémenter `models.py`, récupérer les modèles, les classer par SDR et mettre à jour `MODELS.md`.
- [x] Implémenter `engine.py`, une CLI minimale et un test de bout en bout synthétique.
- [x] Gérer le choix des pistes et des modèles multiples, ainsi que les sorties WAV 24 bits et MP3.
- [x] Créer l'interface PySide6 avec worker `QThread`, sous-processus annulable et glisser-déposer.
- [x] Ajouter les traductions français/anglais et la persistance des préférences.
- [x] Tester l'empaquetage Linux avec PyInstaller et préparer le workflow macOS différé.
