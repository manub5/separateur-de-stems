import hashlib
import json

from scripts.prepare_media import generate_binary_manifest
from separateur_de_stems.core.packaging import validate_redistributed_binary_licences


def test_generate_manifest_uses_installed_binary_hash_and_homebrew_metadata(tmp_path):
    paths = {}
    for name in ("ffmpeg", "ffprobe"):
        target = tmp_path / name
        target.write_bytes(name.encode())
        paths[name] = target
    formula = {
        "name": "ffmpeg",
        "license": "GPL-3.0-or-later",
        "versions": {"stable": "9.0.2"},
        "urls": {"stable": {"url": "https://ffmpeg.org/releases/ffmpeg-9.0.2.tar.xz"}},
        "dependencies": ["x264", "x265"],
    }

    def inspect(command):
        if command[0] == "file":
            return "Mach-O 64-bit executable arm64"
        return f"{command[0].name} version 9.0.2 Copyright"

    manifest_path = tmp_path / "manifest.json"
    generate_binary_manifest(paths, formula, inspect=inspect, output_path=manifest_path)
    data = json.loads(manifest_path.read_text())
    assert {item["name"] for item in data["binaries"]} == {"ffmpeg", "ffprobe"}
    for item in data["binaries"]:
        assert item["source"] == formula["urls"]["stable"]["url"]
        assert item["licence"] == "GPL-3.0-or-later"
        assert item["version"] == "9.0.2"
        assert item["sha256"] == hashlib.sha256(item["name"].encode()).hexdigest()
        assert item["licence_status"] == "not-distributable"
    validate_redistributed_binary_licences(manifest_path, require_distributable=False)


def test_generator_rejects_formula_without_verified_gpl_or_x264_x265(tmp_path):
    paths = {name: tmp_path / name for name in ("ffmpeg", "ffprobe")}
    for path in paths.values():
        path.write_bytes(b"bin")
    formula = {"license": "MIT", "dependencies": []}
    from separateur_de_stems.core.packaging import PackagingError
    import pytest
    with pytest.raises(PackagingError, match="GPL|x264"):
        generate_binary_manifest(paths, formula, inspect=lambda command: "", output_path=tmp_path / "manifest.json")
