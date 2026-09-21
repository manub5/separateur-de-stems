# Plan

- [ ] Créer les fichiers de suivi, la structure du projet, l'environnement virtuel et installer les dépendances avec le contournement `diffq-fixed` documenté.
- [ ] Créer le squelette `core` et les tests unitaires de nommage et d'export.
- [ ] Implémenter `models.py`, récupérer les modèles, les classer par SDR et mettre à jour `MODELS.md`.
- [ ] Implémenter `engine.py`, une CLI minimale et un test de bout en bout synthétique.
- [ ] Gérer le choix des pistes et des modèles multiples, ainsi que les sorties WAV 24 bits et MP3.
- [ ] Créer l'interface PySide6 avec worker `QThread`, sous-processus annulable et glisser-déposer.
- [ ] Ajouter les traductions français/anglais et la persistance des préférences.
- [ ] Tester l'empaquetage Linux avec PyInstaller et préparer le workflow macOS différé.
