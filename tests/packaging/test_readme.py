"""Static checks for the bilingual project README.

The README is project documentation, not shipped code, so it is validated
by reading its raw text: it must exist, carry both the French and English
sections, mention the first-launch workaround for the unsigned macOS app,
and document the CLI, UI and build commands.
"""

from pathlib import Path

README = Path("README.md")


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
