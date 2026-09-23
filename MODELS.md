# Catalogue des modèles retenus

| Piste | Fichier | Type | SDR | Taille | Source | Licence |
|---|---|---|---:|---|---|---|
| vocals | `vocals_mel_band_roformer.ckpt` | MDXC | 12.6 | inconnue | inconnue | inconnue |
| instrumental | `model_bs_roformer_ep_317_sdr_12.9755.ckpt` | MDXC | 16.5 | inconnue | URL consignée dans le manifeste | inconnue |
| drums | `htdemucs_ft.yaml` | Demucs | 10.0 | inconnue | URL consignée dans le manifeste | inconnue |
| bass | `hdemucs_mmi.yaml` | Demucs | 12.2 | inconnue | URL consignée dans le manifeste | inconnue |
| guitar | `htdemucs_6s.yaml` | Demucs | non fourni | inconnue | URL consignée dans le manifeste | inconnue |
| piano | `htdemucs_6s.yaml` | Demucs | non fourni | inconnue | URL consignée dans le manifeste | inconnue |

État versionné : `models/manifest.json` conserve des métadonnées `null` pour les
tailles et SHA-256 qui ne sont pas vérifiés. Il déclare également la
configuration `model_bs_roformer_ep_317_sdr_12.9755.yaml`. Les fichiers sous
`models/` étant ignorés par Git, cette documentation ne conclut rien sur leur
présence dans un checkout particulier.

Les fichiers Demucs `.yaml` du tableau sont des configurations, pas les poids
du modèle. Aucun poids `.th` n'est inventorié dans le manifeste versionné. Le
gate ne peut donc pas prouver qu'un bundle
contient tous les actifs Demucs requis ; cette lacune bloque explicitement la
publication.

Vérification du 2026-09-22 : la présence, le type et les valeurs SDR indiquées
ci-dessus ont été vérifiés dans le catalogue réel d'`audio-separator` 0.47.0.
Les tailles et les licences restent ouvertes et ne sont pas considérées comme
vérifiées. Toute licence inconnue bloque explicitement la diffusion publique ;
les URL du manifeste ne constituent pas une conclusion de licence.
