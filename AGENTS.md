# AGENTS.md — Séparateur de pistes (stems)

## Mission
Construire une application de bureau qui sépare un fichier audio en pistes
(voix, batterie, basse, guitare, piano, reste…), de qualité comparable à
iZotope RX / Ableton Live 12, en s'appuyant UNIQUEMENT sur des bibliothèques
et modèles déjà éprouvés. On n'entraîne aucun modèle, on n'invente aucun
algorithme de séparation.

Cible finale : application `.app` native pour iMac Apple Silicon (M1 et +).
Développement et tests : poste Linux (Kubuntu). Tu travailles en autonomie.

## Règles absolues (non négociables)
1. Tu travailles EXCLUSIVEMENT dans le dossier de ce projet. Aucune lecture,
   écriture ou commande hors de ce dossier.
2. Jamais de `sudo`, jamais d'installation système (apt, etc.), jamais de
   modification de la configuration globale (~/.bashrc, ~/.config, git config --global…).
3. Toutes les dépendances Python vont dans un environnement virtuel local `.venv/`.
   Les modèles téléchargés vont dans `./models/`, les caches dans `./.cache/`.
4. Git : utiliser le .git déjà initié, commits locaux uniquement, un commit par étape terminée, messages clairs.
   JAMAIS de `git push`, JAMAIS de `--no-verify` (les hooks pre-commit/semgrep
   doivent passer ; si un hook échoue, corrige le code).
5. Pour les tests, génère des signaux synthétiques.
6. Si une information manque ou qu'une décision engage le projet, note-la dans
   `QUESTIONS.md` et continue sur le reste plutôt que d'inventer.
7. Vérifie dans la documentation officielle (README, PyPI) toute API avant de
   l'utiliser. Ne suppose pas une signature de fonction.

## Pile technique imposée
- Langage : Python (version la plus récente supportée par TOUTES les dépendances
  ci-dessous — vérifie-la, ne suppose pas).
- Moteur de séparation : `audio-separator` (github.com/nomadkaraoke/python-audio-separator),
  utilisé comme bibliothèque Python. Il donne accès aux modèles UVR :
  BS-RoFormer, Mel-Band RoFormer, MDX, Demucs v4 (dont htdemucs_6s).
- Accélération : détection automatique — MPS/CoreML sur Mac Apple Silicon,
  CUDA si NVIDIA, sinon CPU. Vérifie dans la doc d'audio-separator comment
  il gère Apple Silicon et documente-le.
- Interface : PySide6 (Qt), identique sous Linux et macOS.
- Encodage MP3 : ffmpeg, embarqué dans l'application (pas de dépendance à
  un ffmpeg installé sur l'iMac).
- Empaquetage : PyInstaller (ou alternative si justifiée dans DECISIONS.md).
- Assemblage macOS : GitHub Actions sur runner macOS Apple Silicon (arm64).

## Choix des modèles
- Priorité : qualité maximale, même si c'est lent.
- Utilise le classement SDR fourni par `audio-separator --list_models` pour
  retenir le meilleur modèle PAR type de piste (voix, batterie, basse,
  guitare, piano, instrumental). Privilégie les RoFormer quand ils sont en tête.
- Tous les modèles retenus sont INTÉGRÉS dans l'application (fonctionnement
  hors ligne). Garde la sélection resserrée : pas le catalogue entier.
- Pour chaque modèle retenu, consigne dans `MODELS.md` : nom, piste(s), score
  SDR, taille, source, licence. Signale toute licence incompatible avec une
  diffusion publique dans `QUESTIONS.md`.

## Fonctionnalités
- Glisser-déposer un fichier audio (WAV, FLAC, MP3, AIFF, M4A) ou bouton « Ouvrir ».
- Choix des pistes à extraire par cases à cocher ; l'appli choisit
  automatiquement le(s) modèle(s) adapté(s).
- Choix du dossier de sortie.
- Sortie : WAV 24 bits ET MP3 (320 kb/s) pour chaque piste.
- Barre de progression, bouton Annuler, messages d'erreur compréhensibles.
- Le calcul tourne dans un thread séparé : l'interface ne doit jamais geler.
- Interface bilingue français / anglais, choix dans les réglages (système Qt
  de traduction), mémorisé entre deux lancements.

## Tests (sous Linux, avant chaque commit)
- `pytest` : logique (choix des modèles, nommage des fichiers, formats de sortie).
- Test de bout en bout sur un signal synthétique court avec le modèle le plus
  léger disponible.
- Test de l'interface en mode sans écran (`QT_QPA_PLATFORM=offscreen`).
- Le code macOS-spécifique ne peut pas être testé ici : isole-le et signale-le.

## Livraison macOS
- Workflow `.github/workflows/build-macos.yml` : installe, teste, assemble
  le `.app`, le compresse en `.dmg` ou `.zip`, et le publie comme artefact.
- Application non signée : le README (FR + EN) explique le premier lancement
  sous macOS récent : double-clic → message de blocage → Réglages Système >
  Confidentialité et sécurité → « Ouvrir quand même » → mot de passe.
- Vérifie les limites de taille de fichier de GitHub (artefacts, releases)
  face au poids des modèles intégrés ; propose une solution dans DECISIONS.md
  si elles sont dépassées.

## Méthode de travail
1. Commence par écrire `PLAN.md` : étapes courtes, chacune testable.
2. Ordre conseillé : séparation en ligne de commande → choix des modèles →
   interface → traductions → empaquetage Linux (test) → workflow macOS.
3. Tiens `PROGRESS.md` à jour (fait / en cours / bloqué) à chaque étape.
4. Consigne chaque choix technique non trivial dans `DECISIONS.md` avec sa raison.
5. utilise la skill superpowers pour les tests qualité
