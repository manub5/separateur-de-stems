"""Static checks for the bilingual project README.

The README is project documentation, not shipped code, so it is validated
by reading its raw text: it must exist, carry both the French and English
sections, mention the first-launch workaround for the unsigned macOS app,
and document the CLI, UI and build commands.
"""

from pathlib import Path

README = Path("README.md")
THIRD_PARTY_NOTICES = Path("THIRD_PARTY_NOTICES.md")
IMPLEMENTATION_PLAN = Path(
    "docs/superpowers/plans/2026-09-23-hardening-and-offline-release.md"
)


def _text() -> str:
    return README.read_text(encoding="utf-8")


def _language_sections() -> tuple[str, str]:
    text = _text()
    french_start = text.index("## Français")
    english_start = text.index("## English")
    return text[french_start:english_start], text[english_start:]


def _normalized(text: str) -> str:
    return " ".join(text.split())


def test_readme_exists():
    assert README.is_file()


def test_readme_has_french_and_english_sections():
    text = _text()
    assert "## Français" in text
    assert "## English" in text


def test_readme_documents_unsigned_macos_first_launch():
    french, english = map(_normalized, _language_sections())
    assert "Réglages Système" in french
    assert "Ouvrir quand même" in french
    assert "System Settings" in english
    assert "Open Anyway" in english


def test_readme_documents_cli_and_ui_commands():
    french, english = _language_sections()
    assert "separateur-de-stems morceau.flac" in french
    assert "separateur-de-stems-ui --file morceau.flac" in french
    assert "separateur-de-stems track.flac" in english
    assert "separateur-de-stems-ui --file track.flac" in english


def test_readme_documents_build_commands():
    french, english = _language_sections()
    assert "packaging/build_linux.sh" in french
    assert "build-macos.yml" in french
    assert "packaging/build_linux.sh" in english
    assert "build-macos.yml" in english


def test_each_language_documents_supported_python_range():
    french, english = map(_normalized, _language_sections())
    assert ">=3.12,<3.13" in french
    assert ">=3.12,<3.13" in english


def test_each_language_documents_responsive_lifecycle():
    french, english = map(_normalized, _language_sections())
    assert "L'annulation et la fermeture sont asynchrones" in french
    assert "Cancellation and closing are asynchronous" in english
    assert "QThread.finished" in french
    assert "QThread.finished" in english


def test_each_language_documents_background_pipeline():
    french, english = map(_normalized, _language_sections())
    assert "exports WAV/MP3 s'exécutent hors de l'interface" in french
    assert "espace de travail privé" in french
    assert "WAV/MP3 exports run outside the GUI" in english
    assert "private workspace" in english


def test_each_language_documents_blocked_publication():
    french, english = map(_normalized, _language_sections())
    assert "PUBLICATION BLOQUÉE" in french
    assert "PUBLIC RELEASE BLOCKED" in english


def test_each_language_documents_all_release_blockers():
    french, english = map(_normalized, _language_sections())
    assert "poids Demucs" in french
    assert "licences, sources et versions des binaires" in french
    assert "macos-arm64-transitive.lock" in french
    assert "MPS/CoreML, `renamex_np` et le `.app` final restent non vérifiés" in french
    assert "required Demucs weights" in english
    assert "licences, sources, and versions of redistributed binaries" in english
    assert "macos-arm64-transitive.lock" in english
    assert "MPS/CoreML, `renamex_np`, and the final `.app` remain unverified" in english


def test_readme_distinguishes_offline_release_from_development_downloads():
    french, english = _language_sections()
    french = _normalized(french)
    english = _normalized(english)
    assert "`audio-separator` peut télécharger" in french
    assert "`audio-separator` may download" in english
    assert "bundle de publication vise un fonctionnement hors ligne" in french
    assert "release bundle targets offline operation" in english


def test_readme_does_not_claim_successful_release():
    text = _text().lower()
    assert "publié comme artefact" not in text
    assert "published as an artifact" not in text


def test_third_party_notices_records_only_verified_and_pending_statuses():
    text = THIRD_PARTY_NOTICES.read_text(encoding="utf-8")
    assert "audio-separator 0.47.0" in text
    assert "PySide6 6.11.2" in text
    assert "soundfile 0.14.0" in text
    assert "ffmpeg / ffprobe: pending" in text
    assert "Selected UVR models: pending" in text
    assert "No public release is permitted" in text


def test_release_documents_record_demucs_and_task_status_honestly():
    models = Path("MODELS.md").read_text(encoding="utf-8")
    progress = Path("PROGRESS.md").read_text(encoding="utf-8")
    decisions = Path("DECISIONS.md").read_text(encoding="utf-8")
    assert "`.th`" in models
    assert "pas complètement inventoriés" in models
    assert "état antérieur, supersédé" in progress
    assert "Task 4" in progress.partition("## Fait")[2].partition("## À faire")[0]
    assert "Task 5" in progress.partition("## À faire")[2].partition("## Bloqué")[0]
    assert "## D-011 — Packaging PyInstaller et gates de publication" in decisions


def test_implementation_plan_matches_completed_task_status():
    plan = IMPLEMENTATION_PLAN.read_text(encoding="utf-8")
    completed = plan.partition("### Task 1:")[2].partition("### Task 5:")[0]
    remaining = plan.partition("### Task 5:")[2]
    assert "- [ ]" not in completed
    assert completed.count("- [x]") == 22
    assert "- [x]" not in remaining
    assert remaining.count("- [ ]") == 7
