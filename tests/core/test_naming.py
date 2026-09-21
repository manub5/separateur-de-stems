from pathlib import Path

from separateur_de_stems.core.naming import sanitize, stem_filename, unique_path


def test_sanitize_replaces_all_forbidden_characters() -> None:
    assert sanitize('a<>b:"c/d\\e|f?g*h') == "a__b__c_d_e_f_g_h"


def test_sanitize_preserves_spaces_and_accents() -> None:
    assert sanitize("Ma chanson été") == "Ma chanson été"


def test_unique_path_leaves_available_path_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "song.wav"

    assert unique_path(str(path)) == str(path)


def test_unique_path_adds_first_available_suffix(tmp_path: Path) -> None:
    path = tmp_path / "song.wav"
    path.touch()

    assert unique_path(str(path)) == str(tmp_path / "song_1.wav")


def test_unique_path_skips_existing_suffixes(tmp_path: Path) -> None:
    path = tmp_path / "song.wav"
    path.touch()
    (tmp_path / "song_1.wav").touch()

    assert unique_path(str(path)) == str(tmp_path / "song_2.wav")


def test_stem_filename_builds_complete_sanitized_path(tmp_path: Path) -> None:
    result = stem_filename(
        "/music/My: Song.flac", "lead:vocal", "wav", str(tmp_path)
    )

    assert result == str(tmp_path / "My_ Song_lead_vocal.wav")


def test_stem_filename_normalizes_extension_with_leading_dot(tmp_path: Path) -> None:
    result = stem_filename("song.mp3", "vocals", ".wav", str(tmp_path))

    assert result == str(tmp_path / "song_vocals.wav")


def test_stem_filename_uses_unique_path(tmp_path: Path) -> None:
    (tmp_path / "song_vocals.wav").touch()

    result = stem_filename("song.mp3", "vocals", "wav", str(tmp_path))

    assert result == str(tmp_path / "song_vocals_1.wav")
