# Spec — Séparateur de pistes, phase 2 (UI, i18n, packaging)

Date : 2026-09-22
Statut : validé (brainstorming)
Précède : `2026-09-21-separateur-de-stems-design.md` (phase 1 CLI)

## 1. Objectif

Transformer le pipeline CLI existant (phase 1, fusionnée dans `master`) en
application de bureau : fenêtre PySide6 réactive, glisser-déposer, choix des
pistes, progression, annulation, traductions FR/EN, puis empaquetage.

Le moteur `core/` de la phase 1 est stable et testé (141 tests) ; cette phase
l'utilise sans le réécrire, sauf ajouts bornés listés en §5.

## 2. Décisions de cadrage (issues du brainstorming)

| Sujet | Décision |
|---|---|
| Découpage | **Un spec unique, trois plans d'implémentation successifs** : UI → i18n → packaging |
| Progression | **Par étape/modèle** (pas de granularité intra-modèle) ; barre indéterminée entre étapes |
| Worker UI | **QThread pilote `SubprocessSeparator`** (sous-processus spawn tuable déjà testé) |
| Préférences | **QSettings** + chemins adaptatifs dev vs `.app` |
| Sorties | **WAV 24 bits + MP3 320 par piste**, dans un **sous-dossier par morceau** |
| Disposition | **Fenêtre unique compacte** |
| i18n | Chaînes en `tr()` dès l'UI ; `.ts`/`.qm` par `pylupdate6`/`lrelease` (PySide6, sans outil système) |
| Tests UI | `QT_QPA_PLATFORM=offscreen` + **pytest-qt** (recommandé) |
| Packaging | PyInstaller Linux (test local) ; workflow macOS **différé** ; modèles hors bundle pour l'instant |

## 3. Architecture

```
separateur_de_stems/
├── core/                 # inchangé (Qt-free, testé) + 3 ajouts bornés (§5)
├── ui/
│   ├── app.py            # entrée Qt : QApplication, i18n init, fenêtre
│   ├── main_window.py    # fenêtre unique compacte
│   ├── worker.py         # QThread pilotant SubprocessSeparator
│   ├── drop_zone.py      # zone de glisser-déposer
│   ├── settings.py       # QSettings (langue, chemins, pistes)
│   └── paths.py          # résolution dev vs .app (Application Support)
├── cli.py                # façade CLI existante
└── i18n/                 # .ts sources + .qm générés (Plan B)
```

Principes :

- `ui/` ne contient **aucune logique métier** : il compose `core` et traduit les
  statuts du sous-processus en signaux Qt.
- `core/` reste sans dépendance Qt.
- Deux façades (`cli.py`, `ui/app.py`), un moteur.
- La CI et les hooks existants continuent de s'appliquer ; un commit par étape.

## 4. Interface (Plan A)

**Fenêtre unique compacte** (~520×480, redimensionnable), de haut en bas :

1. **Zone de dépôt** — « Glissez un fichier audio ici » ou le fichier chargé
   (nom, format, durée). Bouton « Ouvrir… » (filtre WAV/FLAC/MP3/AIFF/M4A).
   Drag&drop : premier fichier valide ; fichier invalide → erreur non bloquante.
2. **Choix des pistes** — 6 cases (Voix, Instrumental, Batterie, Basse,
   Guitare, Piano), défaut Voix + Instrumental. Les modèles sont déduits par
   `models.select_models` (guitare/piano partagent `htdemucs_6s`, dédup gérée).
3. **Dossier de sortie** — champ + bouton « Choisir… ». Défaut : préférence, ou
   dossier utilisateur adapté à la plateforme. Sous-dossier par morceau créé
   automatiquement (`<sortie>/<morceau>/`).
4. **Actions** — bouton principal « Séparer » (désactivé sans fichier/piste),
   devient « Annuler » pendant l'exécution.
5. **Progression & journal** — barre (par étape/modèle), libellé d'étape
   (« Séparation 2/3 : voix »), journal concis (2-3 lignes).
6. **Menus** — Fichier (Ouvrir, Quitter), Édition > Réglages (dossier modèles,
   langue), Aide > À propos.

**États** : idle → fichier chargé → en cours (Annuler actif, entrées
verrouillées) → terminé (proposer d'ouvrir le dossier) / erreur / annulé.

## 5. Concurrence, progression, annulation

```
[UI thread]                      [QThread SeparationWorker]        [subprocess spawn]
Separer ──► worker.start()
            worker.run():
              sep = SubprocessSeparator(..., progress_queue=True)
              sep.start(input, stems)
              boucle: sep.poll(timeout=0.1)
                ├─ progress_queue.get_nowait() ──► emit progress(int,str)
                └─ statut ──► emit finished(dict) / error(str) / cancelled()
Annuler ──► worker.request_cancel() ──► sep.cancel() (thread-safe)
```

- Le worker ne touche aucun widget ; tout passe par signaux Qt.
- Pendant l'inférence, l'UI reste fluide ; le bouton devient « Annuler ».
- **Progression** : par étape/modèle ; barre indéterminée entre étapes.
  Limite assumée : pas de granularité intra-modèle (audio-separator n'expose
  aucun callback).
- **Annulation** : `request_cancel()` thread-safe → `cancel()` →
  `terminate`, puis `kill` ; l'UI affiche « Annulé » et nettoie les fichiers
  partiels du run courant.
- **Fin normale** : `dict{stem: path}` → regroupement dans le sous-dossier du
  morceau ; proposition d'ouvrir le dossier.

**Ajouts bornés à `core/` (testables sans Qt)** :

- `SubprocessSeparator.start()` : garde de re-entrée (`RuntimeError` si un run
  est déjà en cours).
- Drain robuste (remplacer le délai fixe `_DRAIN_TIMEOUT` par une attente fiabilisée).
- `progress_queue` optionnelle : le sous-processus y dépose `(percent, stage)` ;
  la CLI ne la passe pas (aucun changement de comportement).

## 6. i18n & persistance (Plan B)

- Toutes les chaînes UI via `self.tr("...")` dès le Plan A.
- Extraction/traduction : `pylupdate6` → `.ts`, `lrelease` → `.qm`, via
  PySide6 (pas de dépendance système). Script `scripts/build_translations.py`.
- Langue source : anglais (chaînes `tr()` en anglais) ; `i18n/*_fr.ts` en
  traduction, `i18n/*_en.ts` éventuellement vide.
- `.qm` générés **committés** (nécessaires hors-ligne au `.app`).
- Réglages : combo « Système / Français / English », mémorisé en `QSettings`,
  appliqué via `QTranslator.load()` (sans redémarrage si possible, sinon
  redémarrage — tranché à l'implémentation).
- Messages `core`/CLI : i18n **hors périmètre** (restent français).

**QSettings** — clés : `language`, `last_input_dir`, `last_output_dir`,
`model_dir`, `default_stems`. Emplacement natif Qt. `ui/paths.py` résout les
chemins selon dev vs `.app` figé (modèles/cache dans un dossier utilisateur en
`.app`, `./models` et `./.cache` en dev).

## 7. Packaging (Plan C)

- Entrée : `separateur_de_stems/ui/app.py:main()` ; cible
  `[project.scripts] separateur-de-stems-ui`.
- **PyInstaller Linux (test local)** : spec `packaging/stem-separator.spec`,
  `--windowed`, collecte PySide6 + audio-separator + données Qt ; binaire
  lançable hors venv.
- **macOS** : `.github/workflows/build-macos.yml` sur runner `macos-14`
  (arm64) — install, tests, `.app`, zip/dmg, artefact. **Différé** : local
  d'abord.
- **ffmpeg** : embarqué (`--add-binary`), chemin résolu au runtime via
  `sys._MEIPASS`.
- **README FR + EN** : premier lancement macOS non signé (Réglages Système >
  Confidentialité > « Ouvrir quand même »).
- **Modèles** : hors bundle pour l'instant (Q-002/Q-003).

## 8. Tests

- **UI headless** : `QT_QPA_PLATFORM=offscreen` + pytest-qt (fixtures `qtbot`).
- **Tests UI sans inférence** : construction de fenêtre, états des boutons,
  drag&drop par événements simulés, worker avec `SubprocessSeparator` mocké →
  émission de `progress`/`finished`/`error`/`cancelled`, activation d'Annuler.
- **Tests `core` ajoutés** : re-entrée `start()`, drain robuste, progression via
  queue — sans Qt.
- **macOS** : non testable ici → isolé, skip, signalé dans `PROGRESS.md`.
- **Emballage** : test PyInstaller local ; le workflow macOS fait office de test
  packaging.

## 9. Hors périmètre

- Traitement par lot / file d'attente de plusieurs morceaux.
- i18n des messages `core`/CLI.
- Embarquement des modèles dans le bundle (Q-002/Q-003).
- Signature/notarisation macOS.
- CI Linux dédiée.

## 10. Décisions à revisiter (héritées de la phase 1)

- Normalisation des chemins relatifs de sortie (`_resolve_output`).
- Déclarer `numpy` explicitement dans `pyproject.toml`.
- Modèle E2E `model_dir` relatif.
- Licences des modèles (Q-004).
