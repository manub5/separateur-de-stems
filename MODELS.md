# Catalogue des modèles retenus

| Piste | Fichier | Type | SDR | Taille | Source | Licence |
|---|---|---|---:|---|---|---|
| vocals | `vocals_mel_band_roformer.ckpt` | MDXC | 12.6 | inconnue | inconnue | inconnue |
| instrumental | `model_bs_roformer_ep_317_sdr_12.9755.ckpt` | MDXC | 16.5 | inconnue | URL consignée dans le manifeste | inconnue |
| drums | `htdemucs_ft.yaml` | Demucs | 10.0 | inconnue | URL consignée dans le manifeste | inconnue |
| bass | `hdemucs_mmi.yaml` | Demucs | 12.2 | inconnue | URL consignée dans le manifeste | inconnue |
| guitar | `htdemucs_6s.yaml` | Demucs | non fourni | inconnue | URL consignée dans le manifeste | inconnue |
| piano | `htdemucs_6s.yaml` | Demucs | non fourni | inconnue | URL consignée dans le manifeste | inconnue |

État local vérifié : `models/` contient uniquement `manifest.json` et
`download_checks.json`; aucun poids sélectionné n'est présent. Le manifeste
exige en plus la configuration
`model_bs_roformer_ep_317_sdr_12.9755.yaml`, elle aussi absente. Les tailles et
SHA-256 ne peuvent donc pas être calculés localement.

Vérification du 2026-09-22 : la présence, le type et les valeurs SDR indiquées
ci-dessus ont été vérifiés dans le catalogue réel d'`audio-separator` 0.47.0.
Les tailles et les licences restent ouvertes et ne sont pas considérées comme
vérifiées. Toute licence inconnue bloque explicitement la diffusion publique ;
les URL du manifeste ne constituent pas une conclusion de licence.
