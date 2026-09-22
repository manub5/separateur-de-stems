# Spec — Séparateur de pistes, Plan B (internationalisation)

Date : 2026-09-22
Statut : validé (brainstorming)
Précède : `2026-09-22-phase2-ui-design.md` (phase 2, spec global), Plan A (UI)

## 1. Objectif

Rendre l'interface bilingue français / anglais : extraction des chaînes de
l'UI, traduction française, chargement au lancement selon la préférence, et
application **à chaud** sans redémarrage. Les messages de `core`/CLI restent
hors périmètre (spec phase 2 §6).

## 2. Décisions de cadrage

| Sujet | Décision |
|---|---|
| Emplacement | `separateur_de_stems/ui/i18n/` (données du paquet) |
| Fichiers | `.ts` source versionné + `.qm` compilé **committé** (hors-ligne) |
| Langue source | **anglais** (chaînes `tr()` déjà en anglais) ; seul un `.qm` FR est produit |
| « Système » | détecte `QLocale.system()` : français → charge le FR, sinon anglais |
| Application | **à chaud** : `install_translators` + `retranslate_ui()` via `QEvent.LanguageChange` |
| Build | `scripts/build_translations.py` (lupdate + lrelease), chemins portables |
| Périmètre | UNIQUEMENT les chaînes de l'UI Qt (~53 `tr()`) |

## 3. Composants

### 3.1 `separateur_de_stems/ui/i18n/` (données)
- `stem_separator_fr.ts` — traductions françaises, versionné.
- `stem_separator_fr.qm` — compilé, committé.
- Peuplé par `pyside6-lupdate` (extraction) et `pyside6-lrelease` (compilation).

### 3.2 `separateur_de_stems/ui/i18n.py`
- `available_languages() -> list[str]` → `["system", "fr"]` (+ « en » implicite).
- `i18n_dir() -> Path` — `ui/i18n/` en dev ; sous `sys._MEIPASS` en bundle.
- `resolve_language(setting: str) -> str | None` — `"system"` → `"fr"` si la
  locale système est française, sinon `None` ; `"fr"` → `"fr"` ; `"en"` → `None`.
- `install_translators(app, setting) -> str` — retire tout `QTranslator`
  précédent, charge le `.qm` si nécessaire, l'installe, retourne la langue
  effective (`"fr"`/`"en"`). Conserve une référence au traducteur installé.
- Repli robuste : `.qm` absent/illisible → anglais, sans crash (log).

## 4. Application à chaud

- `SettingsDialog` : émet `languageChanged = Signal(str)` quand `accept()`
  change la langue ; `retranslate_ui()` réapplique ses textes.
- `MainWindow` : `retranslate_ui()` réapplique titre, menus, boutons, libellés
  des cases, placeholders, textes d'état, libellé de la drop zone ;
  `changeEvent(QEvent.Type.LanguageChange)` appelle `retranslate_ui()`.
- `open_settings()` : après acceptation, si la langue change → persiste dans
  `Settings`, `install_translators(app, setting)`, Qt diffuse `LanguageChange`.
- `DropZone.retranslate_ui()` : réapplique l'invite ou le nom du fichier courant.
- Une séparation en cours n'est pas interrompue par un changement de langue.

## 5. Build & empaquetage

- `scripts/build_translations.py` : localise `pyside6-lupdate`/`pyside6-lrelease`
  (`shutil.which` + repli sur le `bin` de l'interpréteur), extrait les `tr()` de
  `ui/`, compile le `.ts` en `.qm`. Option `--check` (échoue si les `.qm`
  seraient modifiés, sans écrire). Code retour non nul en cas d'échec.
- `pyproject.toml` : `[tool.setuptools.package-data]` inclut `i18n/*.qm` et
  `i18n/*.ts` pour que PyInstaller embarque les données.
- `i18n_dir()` résout dev vs bundle.

## 6. Tests

- `tests/ui/test_i18n.py` : `resolve_language` (system fr/en, fr, en) avec mock
  de `QLocale.system()` ; `install_translators` retourne la langue effective et
  retire proprement ; le `.qm` FR existe et est lisible.
- `tests/ui/test_i18n_integration.py` : après installation du traducteur FR, un
  texte connu change (valide le `.qm` compilé réellement).
- `tests/ui/test_translations_build.py` : fonctions testables du script ;
  compilation dans un dossier temporaire (sans écraser les fichiers committés).
- Extension de `test_main_window.py` / `test_settings_dialog.py` :
  `retranslate_ui()` met à jour les libellés ; `SettingsDialog` émet
  `languageChanged` ; application sans redémarrage.
- Tous headless (`QT_QPA_PLATFORM=offscreen`), sans inférence ni réseau.

## 7. Hors périmètre

- i18n des messages `core`/CLI.
- Autres langues que FR/EN.
- Traduction des noms de modèles.
- Plan C (packaging) : l'embarquement effectif des `.qm` y sera vérifié.
