import json
import os
from pathlib import Path

import pytest

from separateur_de_stems.core import packaging as packaging_mod
from separateur_de_stems.core.packaging import PackagingError, validate_build_inputs
from scripts.smoke_bundle import smoke_ffmpeg


def _executable(path: Path, content="#!/bin/sh\nexit 0\n") -> Path:
    path.write_text(content)
    path.chmod(0o755)
    return path


def _binary_manifest(path, status="distributable"):
    path.write_text(json.dumps({
        "schema_version": 1,
        "binaries": [
            {"name": name, "licence": "LGPL-2.1-or-later", "licence_status": status}
            for name in ("ffmpeg", "ffprobe")
        ],
    }))
    return path


def test_build_inputs_reject_non_executable_tool(tmp_path):
    tool = tmp_path / "ffmpeg"
    tool.write_text("binary")
    assert not os.access(tool, os.X_OK)
    with pytest.raises(PackagingError, match="executable"):
        validate_build_inputs(tmp_path, tmp_path, tool, tool, tmp_path / "licenses.json")


@pytest.mark.parametrize("contents", [b"", b"other"])
def test_build_inputs_require_nonempty_french_translation(tmp_path, contents):
    ffmpeg = _executable(tmp_path / "ffmpeg")
    ffprobe = _executable(tmp_path / "ffprobe")
    i18n = tmp_path / "i18n"
    i18n.mkdir()
    (i18n / "stem_separator_fr.qm").write_bytes(contents)
    if contents == b"other":
        (i18n / "stem_separator_fr.qm").unlink()
        (i18n / "other.qm").write_bytes(contents)
    with pytest.raises(PackagingError, match="stem_separator_fr.qm"):
        validate_build_inputs(tmp_path, i18n, ffmpeg, ffprobe, tmp_path / "licenses.json")


def test_redistributed_binary_licences_must_cover_both_tools(tmp_path):
    manifest = _binary_manifest(tmp_path / "licenses.json")
    data = json.loads(manifest.read_text())
    data["binaries"].pop()
    manifest.write_text(json.dumps(data))
    with pytest.raises(PackagingError, match="ffprobe"):
        packaging_mod.validate_redistributed_binary_licences(manifest)


def test_redistributed_binary_licence_status_blocks_distribution(tmp_path):
    manifest = _binary_manifest(tmp_path / "licenses.json", status="unknown")
    with pytest.raises(PackagingError, match="not distributable"):
        packaging_mod.validate_redistributed_binary_licences(manifest)


def test_redistributed_binary_manifest_rejects_wrong_top_level_type(tmp_path):
    manifest = tmp_path / "licenses.json"
    manifest.write_text("[]")
    with pytest.raises(PackagingError, match="schema"):
        packaging_mod.validate_redistributed_binary_licences(manifest)


def test_macos_release_lock_requires_real_hashes(tmp_path):
    direct_inventory = tmp_path / "macos-arm64.lock"
    direct_inventory.write_text("PySide6==6.11.2\n")
    with pytest.raises(PackagingError, match="transitive.*hash",):
        packaging_mod.validate_macos_release_lock(direct_inventory)


def test_macos_release_lock_accepts_hashed_inventory(tmp_path):
    lock = tmp_path / "transitive.lock"
    lock.write_text("dependency==1.0 --hash=sha256:" + "a" * 64 + "\n")
    assert packaging_mod.validate_macos_release_lock(lock) == lock


def test_macos_release_lock_rejects_malformed_hash(tmp_path):
    lock = tmp_path / "transitive.lock"
    lock.write_text("dependency==1.0 --hash=sha256:not-a-hash\n")
    with pytest.raises(PackagingError, match="transitive.*hash"):
        packaging_mod.validate_macos_release_lock(lock)


def test_ffmpeg_smoke_runs_controlled_executable_without_system_path(tmp_path):
    ffmpeg = _executable(
        tmp_path / "ffmpeg",
        '#!/bin/sh\ntest -z "$PATH" || exit 12\nprintf mp3 > "$7"\n',
    )
    smoke_ffmpeg(ffmpeg, tmp_path)
    assert (tmp_path / "synthetic.mp3").read_bytes() == b"mp3"


def test_ffmpeg_smoke_rejects_executable_that_produces_no_mp3(tmp_path):
    ffmpeg = _executable(tmp_path / "ffmpeg")
    with pytest.raises(PackagingError, match="did not produce"):
        smoke_ffmpeg(ffmpeg, tmp_path)
