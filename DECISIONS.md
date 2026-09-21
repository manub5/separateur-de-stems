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
