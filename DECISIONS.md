# Décisions techniques

## D-001 — Python 3.12

Raison : version présente (3.12.3) et supportée par audio-separator 0.47.0
(>=3.10, hors 3.14.1), torch et PySide6.

## D-002 — Installation locale de audio-separator via diffq-fixed

Raison : les headers Python (`Python.h`) sont absents du système et `sudo`/`apt`
sont interdits. `diffq` (dépendance Linux) ne compile pas. `diffq-fixed` fournit
un wheel cp312 manylinux et satisfait l'import `diffq`. Installation :
`pip install diffq-fixed` puis `pip install audio-separator --no-deps` et les
dépendances manuelles (dont `audioread`, non déclarée).

## D-003 — Catalogue de modèles via get_simplified_model_list

Raison : l'API n'expose pas `list_models()`. `get_simplified_model_list(
filter_sort_by=stem)` renvoie un dictionnaire
`{filename: {Name, Type, Stems, SDR}}`, filtré et trié par SDR décroissant pour
la piste demandée.

## D-004 — Annulation par sous-processus tuable

Raison : audio-separator n'expose aucun point d'interruption ni callback de
progression. La progression sera par étape/modèle ; l'annulation tuera un
sous-processus exploité en phase UI.

## D-005 — Guitare et piano sans modèle spécialisé

Raison : le catalogue ne propose que `htdemucs_6s.yaml` pour ces pistes, sans
score SDR. Cette limite est signalée dans `QUESTIONS.md`.

## D-006 — Export sans fichier temporaire ni rename

Raison : `to_wav24` et `to_mp3_320` écrivent directement la destination. Avec
`ffmpeg -y`, une destination préexistante peut être tronquée avant un échec, et
elle n'est alors pas restaurée (le nettoyage ne supprime que les fichiers créés
par l'appel courant). Accepté en phase 1 car la CLI écrit toujours des chemins
uniques et neufs via `unique_path`. À revoir (temp + rename atomique) si un jour
l'écrasement de fichiers existants devient un cas d'usage.

## D-007 — Résolution des chemins de sortie par l'engine

Raison : `audio_separator` 0.47.0 renvoie, pour les modèles MDXC, des noms de
fichiers relatifs (sans le dossier de sortie) malgré une docstring annonçant
des chemins complets, alors que d'autres backends renvoient des chemins
absolus. `SeparationEngine._collect` résout désormais toute sortie relative
contre `output_dir` via `_resolve_output`, afin que le dict retourné contienne
toujours des chemins exploitables (nécessaire pour l'E2E et la future UI).

## D-008 — Chemins dev vs bundle via QStandardPaths

Raison : en développement, `models/` et `.cache/` restent relatifs au projet.
Dans un bundle PyInstaller, l'application est lancée depuis un dossier
potentiellement non inscriptible : les modèles et le cache vont alors sous
`AppDataLocation/StemSeparator`, et le dossier de sortie par défaut est
`MusicLocation` (repli `DocumentsLocation`, puis `Path.home()`). Le ffmpeg
embarqué est cherché sous `sys._MEIPASS/ffmpeg`. Les branches « frozen » ne sont
testables que par mocks sous Linux, à revérifier sur le bundle macOS.

## D-009 — Worker QThread pilote `SubprocessSeparator`

Raison : `audio-separator` n'expose aucun callback de progression ni point
d'interruption (cf. D-004). `SeparationWorker` (sous-classe `QThread`) pilote
donc un `SubprocessSeparator` : il lance le sous-processus, le sonde par
`poll(timeout)` en boucle, remonte la progression par une queue `spawn`, et
traduit l'état final en signaux Qt (`progress`, `finished`, `failed`,
`cancelled`). L'annulation passe par `request_cancel()`, qui positionne un
`threading.Event` et appelle `cancel()` sur le sous-processus, tuable à tout
moment. La logique de séparation reste dans le cœur : le worker ne fait que
transporter signaux et statut, et l'interface ne gèle jamais.

## D-010 — Tests UI headless via pytest-qt + `QT_QPA_PLATFORM=offscreen`

Raison : l'interface doit être testable sans écran, notamment en CI Linux.
`pytest-qt` fournit `qtbot` (ajout/enlèvement des widgets, `waitSignal`) et le
plateforme Qt `offscreen` évite tout serveur X. Les tests injectent une fausse
usine de worker et/ou mockent `SubprocessSeparator`, donc aucune inférence,
aucun sous-processus réel et aucun accès réseau ne se produisent. Les
`Settings` sont instanciés avec une paire organisation/application isolée
(`TestOrg`/`TestApp`) puis `clear()` pour ne jamais toucher la configuration
réelle de l'utilisateur. Le test de fumée ne lance jamais la boucle
d'événements partagée : `QApplication.exec` est remplacé par un stub, car
appeler `quit()` sur l'instance partagée corromprait les `waitSignal` des tests
suivants (pollution inter-tests observée puis corrigée).

## D-011 — Packaging PyInstaller et gates de publication

Raison : livrer une application autonome sans dépendance à un ffmpeg ou un
Python installés sur la machine cible, tout en gardant un bundle raisonnable.

- **`onedir`** (pas `onefile`) : démarrage plus rapide, chargement des
  bibliothèques Qt/torch sans extraction temporaire, et arborescence
  inspectable — `dist/StemSeparator/StemSeparator` sous Linux,
  `StemSeparator.app` sous macOS.
- **Modèles intégrés au bundle de publication** : le build est refusé tant que
  chaque modèle sélectionné, sa configuration et les métadonnées du manifeste
  ne sont pas complets. En développement seulement, `models/` ou un override
  utilisateur validé peut fournir les actifs locaux (cf. D-012).
- **ffmpeg embarqué** : la spécification intègre le binaire ffmpeg et
  `core.platform.ffmpeg_executable` le résout sous
  `sys._MEIPASS/ffmpeg/ffmpeg` en build figé, sinon retombe sur le `PATH`
  (cf. D-008). `core.platform.ensure_bundled_ffmpeg_on_path` place en outre le
  dossier ffmpeg en tête de `os.environ["PATH"]` et configure
  `pydub.AudioSegment.converter` vers le binaire, car `audio-separator` appelle
  `subprocess.check_output(["ffmpeg", "-version"])` et pydub résout ffmpeg via
  le `PATH`. Cette fonction est appelée au début du runtime hook PyInstaller
  (parent et enfants `spawn`) et, défensivement, dans `cli.main` et
  `ui.app.main` ; elle est idempotente et sans effet hors build figé. Aucune
  dépendance à un ffmpeg système pour l'utilisateur final, tant pour la
  séparation que pour l'export MP3.
- **Identifiant de bundle réel** : `io.github.numa91.stemseparator` (dépôt
  `numa91`), au lieu du placeholder `com.example.stemseparator`. Stable et
  unique, il sert d'identité au `.app` macOS et évitera les collisions avec
  d'autres applications lors d'une future signature/notarisation.
- **Inventaire direct strict dans la CI** : le workflow macOS installe les
  versions directes listées dans `requirements/macos-arm64.lock`. Ce fichier ne
  verrouille pas les dépendances transitives et ne garantit donc pas à lui seul
  une résolution identique.
- **Extension `.qm` committée et embarquée** : les catalogues compilés sont
  versionnés puis inclus dans le bundle (package-data
  `separateur_de_stems.ui` = `i18n/*.qm`, `i18n/*.ts`), et
  `scripts/build_translations.py --check` garantit leur fraîcheur en CI.
- **torch CPU/MPS dans la CI macOS** : sur `macos-14` arm64, les roues torch
  par défaut sont CPU/MPS ; aucun extra CUDA n'est installé (la pile CUDA,
  multi-gigaoctets, n'existe que sous Linux). Le bundle Linux local pèse
  environ 5,8 Go précisément parce qu'il embarque la variante CUDA.
- **Gate et futur artefact macOS** : le workflow ne peut produire
  `StemSeparator-macos.zip` via `ditto` qu'après les gates hors ligne. L'upload
  public d'un tag reste désactivé jusqu'à validation des licences et du lock
  transitif hashé. La taille est mesurée avant tout upload.
- **Application non signée** : pas de signature ni de notarisation Apple
  (pas de certificat). Le README FR/EN décrit la procédure de premier lancement
  (Réglages Système > Confidentialité et sécurité > « Ouvrir quand même »).
- **Actions GitHub épinglées par SHA** : toutes les `uses:` sont figées sur un
  SHA de commit (avec la version en commentaire), exigence semgrep et garantie
  de reproductibilité face aux étiquettes mouvantes.

## D-012 — Distribution hors ligne bloquée par manifeste strict

Raison : les poids et licences de la sélection ne sont pas tous disponibles ou
résolus. `models/manifest.json` inventorie donc chaque nom sélectionné et marque
explicitement les champs inconnus. Chaque fichier redistribué est un objet
`assets` avec chemin, taille et SHA-256 ; les références des modèles doivent
couvrir exactement cet inventaire, et chaque modèle Demucs doit référencer au
moins un poids `.th`. La spec PyInstaller refuse le build avant l'analyse tant
qu'un actif, une configuration, une taille, un SHA-256, une
source ou un statut de licence distribuable manque. En développement, le chemin
`models/` et les overrides utilisateur restent disponibles ; un exécutable figé
n'utilise `_MEIPASS/models` par défaut qu'après validation complète du manifeste.
Le contrôle lit les gros poids par blocs pour ne pas les charger en mémoire.

Le workflow macOS utilise l'inventaire direct
`requirements/macos-arm64.lock`, vérifie les outils multimédia arm64, puis
inspecte le bundle et encode un signal synthétique avec un `PATH` vide. Pour un
tag, `scripts.validate_release` exige en plus les licences redistribuables de
ffmpeg/ffprobe. Leur manifeste est lié aux fichiers réels par SHA-256, version,
architecture et politique de dépendances. Sur macOS, `otool -L` n'autorise que
les bibliothèques système et les références internes relocalisables ; une
plateforme d'inspection inconnue bloque. Le gate exige aussi un futur
`requirements/macos-arm64-transitive.lock` avec de vrais hashes, généré et
validé sur macOS arm64. Aucun hash ni lock transitif
n'est fabriqué depuis Linux ; l'upload tag reste bloqué jusque-là.

Le validateur du futur lock accepte uniquement une exigence `nom==version` par
ligne, suivie d'au moins un SHA-256 complet. Il refuse options, includes, URLs,
markers et doublons, exige les mêmes versions directes que l'inventaire, un
ensemble strictement supérieur, ainsi que les transitifs critiques observables
dans l'application : `torch`, `numpy`, `onnxruntime`, `librosa` et `pydub`.
Pour un tag, ce lock est l'unique source passée à pip avec `--require-hashes`.

## D-013 — Backend Qt XCB par défaut sous Linux

Sous KDE Wayland avec une carte NVIDIA, l'interface pouvait présenter des zones
mal redessinées (zébrures disparaissant au survol). Le problème disparaît avec
`QT_QPA_PLATFORM=xcb`. Le point d'entrée graphique définit donc `xcb` avant
la création de `QApplication`, uniquement sous Linux et uniquement lorsque
`QT_QPA_PLATFORM` n'est pas déjà définie. Une valeur explicite, notamment
`offscreen` pour les tests, reste prioritaire ; macOS et Windows ne sont pas
modifiés. Effet de bord intentionnel : le démarrage Linux utilise XCB/XWayland
par défaut plutôt que le backend Wayland natif.
