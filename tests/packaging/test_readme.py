"""Static checks for the bilingual project README.

The README is project documentation, not shipped code, so it is validated
by reading its raw text: it must exist, carry both the French and English
sections, mention the first-launch workaround for the unsigned macOS app,
and document the CLI, UI and build commands.
"""

from pathlib import Path

README = Path("README.md")
THIRD_PARTY_NOTICES = Path("THIRD_PARTY_NOTICES.md")


def _text() -> str:
    return README.read_text(encoding="utf-8")


def test_readme_exists():
    assert README.is_file()


def test_readme_has_french_and_english_sections():
    text = _text()
    assert "## Français" in text
    assert "## English" in text


def test_readme_documents_unsigned_macos_first_launch():
    text = _text()
    assert "Ouvrir quand même" in text
    assert "Open Anyway" in text


def test_readme_documents_cli_and_ui_commands():
    text = _text()
    assert "separateur-de-stems " in text
    assert "separateur-de-stems-ui" in text


def test_readme_documents_build_commands():
    text = _text()
    assert "packaging/build_linux.sh" in text
    assert "build-macos.yml" in text


def test_readme_documents_supported_python_range_in_both_languages():
    text = _text()
    assert text.count(">=3.12,<3.13") == 2


def test_readme_documents_responsive_cancellable_lifecycle_in_both_languages():
    text = _text()
    assert "L'annulation et la fermeture sont asynchrones" in text
    assert "Cancellation and closing are asynchronous" in text
    assert "QThread.finished" in text


def test_readme_documents_offline_release_gate_in_both_languages():
    text = _text()
    assert "PUBLICATION BLOQUÉE" in text
    assert "PUBLIC RELEASE BLOCKED" in text
    assert "models/manifest.json" in text
    assert "packaging/redistributed-binaries.json" in text
    assert "macos-arm64-transitive.lock" in text


def test_readme_does_not_claim_models_download_or_successful_release():
    text = _text().lower()
    assert "téléchargés/cachés au premier usage" not in text
    assert "downloaded/cached on first use" not in text
    assert "publié comme artefact" not in text
    assert "published as an artifact" not in text


def test_readme_documents_unverified_macos_runtime_in_both_languages():
    text = _text()
    assert "MPS/CoreML, `renamex_np` et le `.app` final restent non vérifiés" in text
    assert "MPS/CoreML, `renamex_np`, and the final `.app` remain unverified" in text


def test_third_party_notices_records_only_verified_and_pending_statuses():
    text = THIRD_PARTY_NOTICES.read_text(encoding="utf-8")
    assert "audio-separator 0.47.0" in text
    assert "PySide6 6.11.2" in text
    assert "soundfile 0.14.0" in text
    assert "ffmpeg / ffprobe: pending" in text
    assert "Selected UVR models: pending" in text
    assert "No public release is permitted" in text
