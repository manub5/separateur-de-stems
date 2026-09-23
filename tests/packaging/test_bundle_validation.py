import json
import os
import hashlib
from pathlib import Path

import pytest

from separateur_de_stems.core import packaging as packaging_mod
from separateur_de_stems.core.packaging import PackagingError, validate_build_inputs
from scripts.smoke_bundle import smoke_ffmpeg


def _executable(path: Path, content="#!/bin/sh\nexit 0\n") -> Path:
    path.write_text(content)
    path.chmod(0o755)
    return path


def _binary_manifest(path, binaries=None, status="distributable"):
    binaries = binaries or {}
    path.write_text(json.dumps({
        "schema_version": 1,
        "binaries": [
            {
                "name": name,
                "licence": "LGPL-2.1-or-later",
                "source": "https://example.invalid/ffmpeg",
                "version": "7.1",
                "architecture": "arm64",
                "sha256": hashlib.sha256(binaries.get(name, b"binary")).hexdigest(),
                "dependency_policy": "system-only",
                "licence_status": status,
            }
            for name in ("ffmpeg", "ffprobe")
        ],
    }))
    return path


def test_otool_parser_accepts_only_system_and_relocatable_dependencies():
    output = """/tmp/ffmpeg:\n\t@rpath/libavcodec.dylib (compatibility version 1.0.0)\n\t/usr/lib/libSystem.B.dylib (compatibility version 1.0.0)\n\t/System/Library/Frameworks/CoreMedia.framework/CoreMedia (compatibility version 1.0.0)\n"""
    assert packaging_mod.parse_otool_dependencies(output) == [
        "@rpath/libavcodec.dylib",
        "/usr/lib/libSystem.B.dylib",
        "/System/Library/Frameworks/CoreMedia.framework/CoreMedia",
    ]


@pytest.mark.parametrize("dependency", ["/opt/homebrew/lib/libx.dylib", "/usr/local/lib/libx.dylib", "/tmp/libx.dylib"])
def test_otool_dependency_policy_rejects_external_paths(dependency):
    with pytest.raises(PackagingError, match="external dependency"):
        packaging_mod.validate_macos_dependencies([dependency], "ffmpeg")


def test_binary_validation_binds_manifest_to_real_files(tmp_path):
    payloads = {name: f"{name}-payload".encode() for name in ("ffmpeg", "ffprobe")}
    paths = {}
    for name, payload in payloads.items():
        path = tmp_path / name
        path.write_bytes(payload)
        path.chmod(0o755)
        paths[name] = path
    manifest = _binary_manifest(tmp_path / "binaries.json", payloads)

    def inspect(command):
        if command[0] == "file":
            return "Mach-O 64-bit executable arm64"
        if command[0] == "otool":
            return f"{command[-1]}:\n\t/usr/lib/libSystem.B.dylib (compatibility version 1.0.0)\n"
        return f"{Path(command[0]).name} version 7.1 Copyright"

    packaging_mod.validate_redistributed_binaries(manifest, paths, inspect=inspect, platform_name="darwin")


def test_binary_validation_rejects_version_substring_match(tmp_path):
    payloads = {name: name.encode() for name in ("ffmpeg", "ffprobe")}
    paths = {name: _executable(tmp_path / name, payload.decode()) for name, payload in payloads.items()}
    manifest = _binary_manifest(tmp_path / "binaries.json", payloads)

    def inspect(command):
        if command[0] == "file":
            return "Mach-O 64-bit executable arm64"
        if command[0] == "otool":
            return f"{command[-1]}:\n\t/usr/lib/libSystem.B.dylib (compatibility version 1.0.0)\n"
        return f"{Path(command[0]).name} version 17.1 Copyright"

    with pytest.raises(PackagingError, match="version mismatch"):
        packaging_mod.validate_redistributed_binaries(
            manifest, paths, inspect=inspect, platform_name="darwin"
        )


def _fake_macos_app(tmp_path, *, dependency="@rpath/libcodec.dylib", rpath="@loader_path/../Frameworks"):
    app = tmp_path / "StemSeparator.app"
    executable = app / "Contents" / "MacOS" / "StemSeparator"
    library = app / "Contents" / "Frameworks" / "libcodec.dylib"
    executable.parent.mkdir(parents=True)
    library.parent.mkdir(parents=True)
    executable.write_bytes(b"app")
    library.write_bytes(b"library")
    executable.chmod(0o755)
    outputs = {
        ("file", "-b", str(executable)): "Mach-O 64-bit executable arm64",
        ("file", "-b", str(library)): "Mach-O 64-bit dynamically linked shared library arm64",
        ("otool", "-L", str(executable)): f"{executable}:\n\t{dependency} (compatibility version 1.0.0)\n",
        ("otool", "-L", str(library)): f"{library}:\n\t/usr/lib/libSystem.B.dylib (compatibility version 1.0.0)\n",
        ("otool", "-l", str(executable)): (
            "Load command 0\n      cmd LC_RPATH\n  cmdsize 48\n"
            f"     path {rpath} (offset 12)\n"
        ),
        ("otool", "-l", str(library)): "",
    }

    def inspect(command):
        return outputs[tuple(map(str, command))]

    return app, executable, library, inspect, outputs


def test_macos_bundle_validator_accepts_complete_closure_and_reports_hashes(tmp_path):
    app, executable, library, inspect, _ = _fake_macos_app(tmp_path)
    report = tmp_path / "ignored-runtime-closure.json"

    result = packaging_mod.validate_macos_bundle(app, inspect=inspect, report_path=report)

    assert set(result) == {executable, library}
    data = json.loads(report.read_text())
    library_entry = next(item for item in data["mach_o_files"] if item["path"].endswith("libcodec.dylib"))
    assert library_entry["size"] == len(b"library")
    assert library_entry["sha256"] == hashlib.sha256(b"library").hexdigest()


def test_macos_bundle_validator_rejects_missing_rpath(tmp_path):
    app, _, _, inspect, _ = _fake_macos_app(tmp_path, rpath="@loader_path/missing")
    with pytest.raises(PackagingError, match="unresolved.*@rpath"):
        packaging_mod.validate_macos_bundle(app, inspect=inspect)


def test_macos_bundle_validator_rejects_missing_loader_target(tmp_path):
    app, _, _, inspect, _ = _fake_macos_app(
        tmp_path, dependency="@loader_path/../Frameworks/missing.dylib"
    )
    with pytest.raises(PackagingError, match="missing dependency target"):
        packaging_mod.validate_macos_bundle(app, inspect=inspect)


def test_macos_bundle_validator_rejects_transitive_external_dependency(tmp_path):
    app, _, library, inspect, outputs = _fake_macos_app(tmp_path)
    outputs[("otool", "-L", str(library))] = (
        f"{library}:\n\t/opt/homebrew/lib/libexternal.dylib (compatibility version 1.0.0)\n"
    )
    with pytest.raises(PackagingError, match="external dependency"):
        packaging_mod.validate_macos_bundle(app, inspect=inspect)


def test_binary_validation_fails_closed_when_dependency_inspection_is_unknown(tmp_path):
    payloads = {name: name.encode() for name in ("ffmpeg", "ffprobe")}
    paths = {name: _executable(tmp_path / name, payload.decode()) for name, payload in payloads.items()}
    manifest = _binary_manifest(tmp_path / "binaries.json", payloads)
    with pytest.raises(PackagingError, match="unsupported dependency inspection"):
        packaging_mod.validate_redistributed_binaries(manifest, paths, inspect=lambda command: "", platform_name="linux")


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


def test_redistributed_binary_manifest_invalid_utf8_is_contextual(tmp_path):
    manifest = tmp_path / "licenses.json"
    manifest.write_bytes(b"\xff")
    with pytest.raises(PackagingError, match="binary licence manifest.*UTF-8"):
        packaging_mod.validate_redistributed_binary_licences(manifest)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda data: data["binaries"].append(dict(data["binaries"][0])),
        lambda data: data["binaries"][0].update(extra="unexpected"),
        lambda data: data["binaries"][0].pop("source"),
        lambda data: data["binaries"].__setitem__(0, "ffmpeg"),
        lambda data: data["binaries"][0].update(name=[]),
    ],
)
def test_redistributed_binary_manifest_rejects_adversarial_entries(tmp_path, mutation):
    manifest = _binary_manifest(tmp_path / "licenses.json")
    data = json.loads(manifest.read_text())
    mutation(data)
    manifest.write_text(json.dumps(data))
    with pytest.raises(PackagingError, match="schema|duplicate|fields"):
        packaging_mod.validate_redistributed_binary_licences(manifest)


def _write_inventory(path):
    path.write_text("app-one==1.0\napp-two==2.0\n")
    return path


def _hashed(name, version="1.0", digest="a" * 64):
    return f"{name}=={version} --hash=sha256:{digest}"


def _complete_lock_lines():
    transitives = ["torch", "numpy", "onnxruntime", "librosa", "pydub"]
    return [_hashed("app-one"), _hashed("app-two", "2.0"), *[_hashed(name) for name in transitives]]


def test_macos_release_lock_accepts_hashed_inventory(tmp_path):
    inventory = _write_inventory(tmp_path / "direct.lock")
    lock = tmp_path / "transitive.lock"
    lock.write_text("\n".join(_complete_lock_lines()) + "\n")
    assert packaging_mod.validate_macos_release_lock(lock, inventory) == lock


def test_macos_release_lock_rejects_malformed_hash(tmp_path):
    inventory = _write_inventory(tmp_path / "direct.lock")
    lock = tmp_path / "transitive.lock"
    lines = _complete_lock_lines()
    lines[0] = _hashed("app-one", digest="not-a-hash")
    lock.write_text("\n".join(lines) + "\n")
    with pytest.raises(PackagingError, match="app-one.*hash"):
        packaging_mod.validate_macos_release_lock(lock, inventory)


@pytest.mark.parametrize(
    "bad_line",
    [
        "dependency>=1.0 --hash=sha256:" + "a" * 64,
        "-r other.lock",
        "dependency @ https://example.invalid/pkg.whl --hash=sha256:" + "a" * 64,
        "dependency==1.0; python_version > '3' --hash=sha256:" + "a" * 64,
    ],
)
def test_macos_release_lock_rejects_unsupported_requirement_lines(tmp_path, bad_line):
    inventory = _write_inventory(tmp_path / "direct.lock")
    lock = tmp_path / "transitive.lock"
    lock.write_text("\n".join([*_complete_lock_lines(), bad_line]) + "\n")
    with pytest.raises(PackagingError, match="unsupported"):
        packaging_mod.validate_macos_release_lock(lock, inventory)


def test_macos_release_lock_rejects_duplicate_dependency(tmp_path):
    inventory = _write_inventory(tmp_path / "direct.lock")
    lock = tmp_path / "transitive.lock"
    lines = _complete_lock_lines()
    lock.write_text("\n".join([*lines, lines[0]]) + "\n")
    with pytest.raises(PackagingError, match="duplicate"):
        packaging_mod.validate_macos_release_lock(lock, inventory)


def test_macos_release_lock_requires_all_direct_and_critical_transitives(tmp_path):
    inventory = _write_inventory(tmp_path / "direct.lock")
    lock = tmp_path / "transitive.lock"
    lock.write_text("\n".join(_complete_lock_lines()[:-1]) + "\n")
    with pytest.raises(PackagingError, match="pydub"):
        packaging_mod.validate_macos_release_lock(lock, inventory)

    lock.write_text("\n".join(_complete_lock_lines()[1:]) + "\n")
    with pytest.raises(PackagingError, match="app-one"):
        packaging_mod.validate_macos_release_lock(lock, inventory)


def test_macos_release_lock_preserves_direct_versions(tmp_path):
    inventory = _write_inventory(tmp_path / "direct.lock")
    lock = tmp_path / "transitive.lock"
    lines = _complete_lock_lines()
    lines[0] = _hashed("app-one", version="9.9")
    lock.write_text("\n".join(lines) + "\n")
    with pytest.raises(PackagingError, match="version.*app-one"):
        packaging_mod.validate_macos_release_lock(lock, inventory)


def test_macos_release_lock_must_strictly_exceed_direct_inventory(tmp_path):
    inventory = _write_inventory(tmp_path / "direct.lock")
    lock = tmp_path / "transitive.lock"
    lock.write_text("\n".join([_hashed("app-one"), _hashed("app-two")]) + "\n")
    with pytest.raises(PackagingError, match="strict superset"):
        packaging_mod.validate_macos_release_lock(lock, inventory)


def test_macos_release_lock_invalid_utf8_is_contextual(tmp_path):
    inventory = _write_inventory(tmp_path / "direct.lock")
    lock = tmp_path / "transitive.lock"
    lock.write_bytes(b"\xff")
    with pytest.raises(PackagingError, match="transitive lock.*UTF-8"):
        packaging_mod.validate_macos_release_lock(lock, inventory)


def test_macos_direct_inventory_invalid_utf8_is_contextual(tmp_path):
    inventory = tmp_path / "direct.lock"
    inventory.write_bytes(b"\xff")
    lock = tmp_path / "transitive.lock"
    lock.write_text("\n".join(_complete_lock_lines()) + "\n")
    with pytest.raises(PackagingError, match="direct dependency inventory.*UTF-8"):
        packaging_mod.validate_macos_release_lock(lock, inventory)


@pytest.mark.parametrize(
    "requirement",
    [
        "app-one===1.0",
        "app-one==1.0==extra",
        "app-one>=1.0",
        "app-one==>1.0",
        "app-one==<1.0",
        "app-one==~=1.0",
        "app-one==!=1.0",
        "app-one ==1.0",
        "app-one== 1.0",
    ],
)
def test_macos_direct_inventory_rejects_ambiguous_exact_versions(
    tmp_path, requirement
):
    inventory = tmp_path / "direct.lock"
    inventory.write_text(f"{requirement}\napp-two==2.0\n")
    lock = tmp_path / "transitive.lock"
    lock.write_text("\n".join(_complete_lock_lines()) + "\n")

    with pytest.raises(PackagingError, match="unsupported"):
        packaging_mod.validate_macos_release_lock(lock, inventory)


@pytest.mark.parametrize(
    "requirement",
    [
        "package===1.0 --hash=sha256:" + "a" * 64,
        "package>=1.0 --hash=sha256:" + "a" * 64,
        "package==>1.0 --hash=sha256:" + "a" * 64,
        "package==<1.0 --hash=sha256:" + "a" * 64,
        "package==~=1.0 --hash=sha256:" + "a" * 64,
        "package==!=1.0 --hash=sha256:" + "a" * 64,
        "package==1.0==extra --hash=sha256:" + "a" * 64,
        "package ==1.0 --hash=sha256:" + "a" * 64,
        "package== 1.0 --hash=sha256:" + "a" * 64,
        " package==1.0 --hash=sha256:" + "a" * 64,
        "package==1.0 --hash=sha256:" + "a" * 64 + " ",
    ],
)
def test_macos_release_lock_rejects_ambiguous_exact_versions(tmp_path, requirement):
    inventory = _write_inventory(tmp_path / "direct.lock")
    lock = tmp_path / "transitive.lock"
    lock.write_text("\n".join([*_complete_lock_lines(), requirement]) + "\n")
    with pytest.raises(PackagingError, match="unsupported|invalid"):
        packaging_mod.validate_macos_release_lock(lock, inventory)


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
