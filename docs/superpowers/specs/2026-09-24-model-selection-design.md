# Sélection complète des modèles — conception

## Objectif

Chaque piste proposée sélectionne un modèle du catalogue SDR d'audio-separator
0.47.0 ; chaque modèle dispose d'un ensemble fermé d'actifs locaux vérifiés.
Le manifeste est la source de vérité pour la disponibilité des pistes et pour
les téléchargements. Les fichiers de poids restent ignorés par Git.

## Sélection et données

Le classement obtenu par `audio-separator --list_models --list_format=json`
donne voix Mel-Band RoFormer (12,5967), instrumental BS-RoFormer Gabox
(17,2147), batterie htdemucs_ft (10,0244), basse hdemucs_mmi (12,2277) ;
guitare et piano htdemucs_6s (scores SDR non fournis). Cinq modèles uniques.
Chaque entrée `models` du manifeste relie le nom chargé à la liste complète
des actifs (poids, YAML). Chaque entrée `assets` contient chemin relatif,
URL HTTPS vérifiée, taille en octets et SHA-256. `download_checks.json` est
également vérifié ; la liste des poids Demucs doit correspondre exactement à
ce fichier. Une licence non prouvée reste `unknown` ; elle bloque la diffusion
publique mais pas un build personnel explicitement désigné.

## Téléchargement

`scripts/fetch_models.py` lit et valide le manifeste sans écrire ailleurs que
`./models/`. Un actif déjà valide est ignoré. Un téléchargement partiel est
repris par requête HTTP Range seulement si le serveur confirme `206` et le
bon intervalle ; sinon il repart de zéro sans concaténer des octets douteux.
Le fichier final est remplacé atomiquement après validation taille et SHA-256.
Une URL absente, un serveur indisponible ou une empreinte incorrecte produit
une erreur claire ; les partiels sont conservés pour reprise.

## Application et tests

L'interface vérifie les actifs par piste dans le dossier de modèles sélectionné
et désactive une piste absente avec une explication. Le moteur conserve la
sélection déterministe du catalogue/manifeste et valide avant `load_model`.
Les tests synthétiques par piste remplacent l'inférence lourde par un faux
séparateur : ils vérifient le bon nom de modèle et un fichier audio réellement
produit. Un E2E court avec modèle réel est lancé lorsque les actifs le permettent.

## macOS

Le workflow appelle le script avant PyInstaller. Le gate de build personnel
accepte `licence_status=unknown`, celui des tags reste strict. Le total des
actifs et le poids réel de l'archive sont mesurés et comparés aux limites
documentées ; aucune limite approximative ne doit être présentée comme sûre.
Les autres blockers (binaires et lock transitive) restent explicitement
indépendants de la sélection de modèles.
