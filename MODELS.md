# Modèles retenus (audio-separator 0.47.0)

| Piste | Modèle | SDR | Taille (poids + configuration) | Licence des poids |
|---|---|---:|---:|---|
| Voix | `vocals_mel_band_roformer.ckpt` | 12,5967 | 913 107 844 o | À vérifier |
| Instrumental | `bs_roformer_vocals_gabox.ckpt` | 17,2147 | 639 256 857 o | À vérifier |
| Batterie | `htdemucs_ft.yaml` | 10,0244 | 336 565 233 o (4 poids) | À vérifier |
| Basse | `hdemucs_mmi.yaml` | 12,2277 | 167 407 308 o | À vérifier |
| Guitare | `htdemucs_6s.yaml` | non fourni | 54 996 348 o | À vérifier |
| Piano | `htdemucs_6s.yaml` | non fourni | partagé avec guitare | À vérifier |

Le manifeste `models/manifest.json` donne pour chaque actif (poids `.ckpt` et
`.th`, configurations `.yaml`, index `download_checks.json`) l'URL source,
la taille et le SHA-256 relevés sur le fichier téléchargé. Les six poids
Demucs sont inventoriés. Le total des actifs uniques est 2 111 361 857 octets
(1,966 Gio), avant l'environnement Python, Qt et ffmpeg. Les fichiers de poids
ne sont pas versionnés ; exécuter `python -m scripts.fetch_models` sur un nouveau
checkout. Les licences des poids n'étant pas prouvées, aucune release publique
ne doit être publiée avant leur vérification (Q-004).
