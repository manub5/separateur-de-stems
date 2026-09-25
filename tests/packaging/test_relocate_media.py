import hashlib
import json
from pathlib import Path

import pytest

from scripts.relocate_media import relocate_media
from separateur_de_stems.core.packaging import PackagingError, validate_redistributed_binary_licences, validate_redistributed_binaries


def test_relocation_copies_transitive_homebrew_libs_and_rewrites_paths(tmp_path):
    brew = tmp_path / "brew"
    lib_a = brew / "Cellar" / "ffmpeg" / "9.0.2" / "lib" / "libavcodec.dylib"
    lib_b = brew / "Cellar" / "x264" / "1.2" / "lib" / "libx264.dylib"
    lib_a.parent.mkdir(parents=True)
    lib_b.parent.mkdir(parents=True)
    lib_a.write_bytes(b"codec")
    lib_b.write_bytes(b"x264")
    app = tmp_path / "StemSeparator.app"
    tools = app / "Contents" / "Frameworks" / "ffmpeg"
    tools.mkdir(parents=True)
    binaries = [tools / "ffmpeg", tools / "ffprobe"]
    for binary in binaries:
        binary.write_bytes(binary.name.encode())
        binary.chmod(0o755)
    dependencies = {
        "ffmpeg": [str(lib_a), "/usr/lib/libSystem.B.dylib"],
        "ffprobe": [str(lib_a)],
        "libavcodec.dylib": [str(lib_b)],
        "libx264.dylib": ["/usr/lib/libSystem.B.dylib"],
    }
    commands = []

    def inspect(command):
        if command[:2] == ["otool", "-L"]:
            path = Path(command[-1])
            return f"{path}:\n" + "".join(
                f"\t{name} (compatibility version 1.0.0)\n"
                for name in dependencies[path.name]
            )
        return "Mach-O 64-bit arm64"

    manifest = app / "media.json"
    manifest.write_text(json.dumps({
        "schema_version": 1,
        "binaries": [{
            "name": path.name, "source": "https://example.org/ffmpeg.tar.xz",
            "version": "9.0.2", "licence": "GPL-3.0-or-later",
            "licence_status": "not-distributable", "architecture": "arm64",
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "dependency_policy": "system-only",
        } for path in binaries],
    }))
    relocate_media(
        app, brew, manifest_path=manifest, inspect=inspect,
        rewrite=lambda command: commands.append(command),
        formula_info=lambda name: {"license": "GPL-3.0-or-later" if name == "ffmpeg" else "GPL-2.0-or-later", "urls": {"stable": {"url": f"https://example.org/{name}.tar.xz"}}},
    )
    inside = tools / "lib" / "ffmpeg" / "9.0.2" / "lib" / "libavcodec.dylib"
    inside_b = tools / "lib" / "x264" / "1.2" / "lib" / "libx264.dylib"
    assert inside.read_bytes() == b"codec"
    assert inside_b.read_bytes() == b"x264"
    assert any(cmd[:2] == ["install_name_tool", "-change"] and str(lib_a) in cmd for cmd in commands)
    assert any(cmd[:2] == ["install_name_tool", "-change"] and str(lib_b) in cmd for cmd in commands)
    data = json.loads(manifest.read_text())
    assert len(data["libraries"]) == 2
    assert {entry["sha256"] for entry in data["libraries"]} == {
        hashlib.sha256(b"codec").hexdigest(), hashlib.sha256(b"x264").hexdigest()
    }
    validate_redistributed_binary_licences(manifest, require_distributable=False)
    with pytest.raises(PackagingError, match="not distributable"):
        validate_redistributed_binary_licences(manifest)

    def bundled_inspect(command):
        if command[0] == "file":
            return "Mach-O arm64"
        if command[0] == "otool":
            return f"{command[-1]}:\n\t/usr/lib/libSystem.B.dylib (compatibility version 1.0)\n"
        return f"{Path(command[0]).name} version 9.0.2 Copyright"

    inside_b.write_bytes(b"tampered")
    with pytest.raises(PackagingError, match="library.*SHA-256"):
        validate_redistributed_binaries(
            manifest, {path.name: path for path in binaries}, inspect=bundled_inspect,
            platform_name="darwin", require_distributable=False,
        )


def test_relocation_rejects_external_non_system_dependency(tmp_path):
    brew = tmp_path / "brew"
    app = tmp_path / "StemSeparator.app"
    tools = app / "Contents" / "Frameworks" / "ffmpeg"
    tools.mkdir(parents=True)
    for name in ("ffmpeg", "ffprobe"):
        (tools / name).write_bytes(b"bin")
    manifest = app / "media.json"
    manifest.write_text(json.dumps({"schema_version": 1, "binaries": []}))
    def inspect(command):
        if command[0] == "otool":
            return f"{command[-1]}:\n\t/usr/local/lib/unknown.dylib (compatibility version 1.0)\n"
        return "Mach-O arm64"
    with pytest.raises(PackagingError, match="external dependency"):
        relocate_media(app, brew, manifest_path=manifest, inspect=inspect, rewrite=lambda cmd: None)


def test_relocation_resolves_homebrew_rpath_to_real_library(tmp_path):
    brew = tmp_path / "brew"
    library = brew / "Cellar" / "x264" / "1.2" / "lib" / "libx264.dylib"
    library.parent.mkdir(parents=True)
    library.write_bytes(b"codec")
    app = tmp_path / "App.app"
    tools = app / "Contents" / "Frameworks" / "ffmpeg"
    tools.mkdir(parents=True)
    for name in ("ffmpeg", "ffprobe"):
        (tools / name).write_bytes(b"bin")
    manifest = tools / "redistributed-binaries.json"
    manifest.write_text(json.dumps({"schema_version": 1, "binaries": []}))
    changes = []

    def inspect(command):
        if command[:2] == ["otool", "-l"]:
            return (
                "Load command 0\n      cmd LC_RPATH\n  cmdsize 48\n"
                f"     path {library.parent} (offset 12)\n"
            ) if Path(command[-1]).name == "ffmpeg" else ""
        if command[:2] == ["otool", "-L"]:
            ref = "@rpath/libx264.dylib" if Path(command[-1]).name == "ffmpeg" else "/usr/lib/libSystem.B.dylib"
            return f"{command[-1]}:\n\t{ref} (compatibility version 1.0)\n"
        return "Mach-O arm64"

    relocate_media(
        app, brew, manifest_path=manifest, inspect=inspect,
        rewrite=lambda command: changes.append(command),
        formula_info=lambda name: {"license": "GPL-2.0-or-later", "urls": {"stable": {"url": "https://example.org/source.tar.xz"}}},
    )
    assert any(cmd[1:3] == ["-change", "@rpath/libx264.dylib"] for cmd in changes)
    assert any(cmd[1:3] == ["-delete_rpath", str(library.parent)] for cmd in changes)
    assert (tools / "lib" / "x264" / "1.2" / "lib" / "libx264.dylib").is_file()


def test_dylib_install_id_is_not_mistaken_for_external_dependency(tmp_path):
    brew = tmp_path / "brew"
    library = brew / "Cellar" / "x264" / "1.2" / "lib" / "libx264.dylib"
    library.parent.mkdir(parents=True)
    library.write_bytes(b"codec")
    app = tmp_path / "App.app"
    tools = app / "Contents" / "Frameworks" / "ffmpeg"
    tools.mkdir(parents=True)
    for name in ("ffmpeg", "ffprobe"):
        (tools / name).write_bytes(b"bin")
    manifest = tools / "redistributed-binaries.json"
    manifest.write_text(json.dumps({"schema_version": 1, "binaries": []}))

    def inspect(command):
        if command[:2] == ["otool", "-D"]:
            return f"{command[-1]}:\n@rpath/libx264.dylib\n"
        if command[:2] == ["otool", "-L"]:
            dependency = str(library) if Path(command[-1]).name == "ffmpeg" else (
                "@rpath/libx264.dylib" if Path(command[-1]).name == "libx264.dylib"
                else "/usr/lib/libSystem.B.dylib"
            )
            return f"{command[-1]}:\n\t{dependency} (compatibility version 1.0)\n"
        return "Mach-O arm64"

    relocate_media(
        app, brew, manifest_path=manifest, inspect=inspect,
        rewrite=lambda command: None,
        formula_info=lambda name: {"license": "GPL-2.0-or-later", "urls": {"stable": {"url": "https://example.org/source.tar.xz"}}},
    )
