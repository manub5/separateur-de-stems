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
