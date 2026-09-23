"""Strict checks shared by PyInstaller and packaging smoke scripts."""

import os
import json
import re
from pathlib import Path

from separateur_de_stems.core.bundle_manifest import (
    BundleManifestError,
    PackagingError,
    validate_model_bundle,
)

_BINARY_FIELDS = {"name", "licence", "source", "version", "licence_status"}
_BINARY_NAMES = {"ffmpeg", "ffprobe"}
_LICENCE_STATUSES = {"distributable", "not-distributable", "unknown"}
_REQUIREMENT = re.compile(
    r"(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)==(?P<version>[^\s;@=]+)"
    r"(?P<hashes>(?:\s+--hash=sha256:[0-9a-f]{64})+)"
)
_MALFORMED_HASH_REQUIREMENT = re.compile(
    r"(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)==[^\s;@=]+"
    r"\s+--hash=sha256:\S+"
)
# These are exercised by the application and must appear in a credible lock
# produced from audio-separator and the direct audio/runtime dependencies.
_CRITICAL_MACOS_TRANSITIVES = {"librosa", "numpy", "onnxruntime", "pydub", "torch"}


def validate_build_inputs(models_dir, translations_dir, ffmpeg, ffprobe, binary_licences):
    for name, executable in (("ffmpeg", ffmpeg), ("ffprobe", ffprobe)):
        path = Path(executable) if executable else Path()
        if not executable or not path.is_file() or not os.access(path, os.X_OK):
            raise PackagingError(f"Required {name} executable is absent or not executable: {executable}")
    translation = Path(translations_dir) / "stem_separator_fr.qm"
    if not translation.is_file() or translation.stat().st_size == 0:
        raise PackagingError(f"Required non-empty translation is absent: {translation}")
    validate_redistributed_binary_licences(binary_licences)
    try:
        return validate_model_bundle(models_dir, require_distributable=True)
    except BundleManifestError as error:
        raise PackagingError(f"Offline model manifest is incomplete: {error}") from error


def validate_redistributed_binary_licences(manifest_path):
    try:
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except UnicodeDecodeError as error:
        raise PackagingError(
            f"Redistributed binary licence manifest is not valid UTF-8: {error}"
        ) from error
    except (OSError, json.JSONDecodeError) as error:
        raise PackagingError(f"Redistributed binary licence manifest is invalid: {error}") from error
    if not isinstance(manifest, dict) or set(manifest) != {"schema_version", "binaries"}:
        raise PackagingError("Redistributed binary licence manifest has an unsupported schema")
    entries = manifest["binaries"]
    if manifest["schema_version"] != 1 or not isinstance(entries, list):
        raise PackagingError("Redistributed binary licence manifest has an unsupported schema")
    if not all(isinstance(entry, dict) and set(entry) == _BINARY_FIELDS for entry in entries):
        raise PackagingError("Redistributed binary entries have invalid fields or schema")
    if not all(
        isinstance(entry[field], str) and entry[field]
        for entry in entries
        for field in _BINARY_FIELDS
    ):
        raise PackagingError("Redistributed binary fields must be non-empty strings")
    names = [entry["name"] for entry in entries]
    if len(names) != len(set(names)):
        raise PackagingError("Redistributed binary names must not contain duplicates")
    if set(names) != _BINARY_NAMES:
        missing = ", ".join(sorted(_BINARY_NAMES - set(names)))
        raise PackagingError(f"Redistributed binary manifest has incorrect names; missing {missing}")
    for entry in entries:
        name = entry["name"]
        if entry["licence_status"] not in _LICENCE_STATUSES:
            raise PackagingError(f"Redistributed binary {name} has an invalid licence status")
        if entry.get("licence_status") != "distributable":
            raise PackagingError(f"Redistributed binary {name} is not distributable")
    return Path(manifest_path)


def validate_macos_release_lock(lock_path, direct_inventory_path="requirements/macos-arm64.lock"):
    path = Path(lock_path)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise PackagingError(f"macOS transitive lock is not valid UTF-8: {error}") from error
    except OSError as error:
        raise PackagingError(f"macOS transitive lock with hashes is absent: {error}") from error
    requirements = _parse_requirements(lines, require_hashes=True)
    try:
        direct_lines = Path(direct_inventory_path).read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise PackagingError(
            f"macOS direct dependency inventory is not valid UTF-8: {error}"
        ) from error
    except OSError as error:
        raise PackagingError(f"macOS direct dependency inventory is absent: {error}") from error
    direct = _parse_requirements(direct_lines, require_hashes=False)
    locked_names = set(requirements)
    direct_names = set(direct)
    if len(locked_names) <= len(direct_names):
        raise PackagingError("macOS transitive lock must be a strict superset of direct dependencies")
    missing_direct = direct_names - locked_names
    if missing_direct:
        raise PackagingError(f"macOS transitive lock is missing direct dependencies: {', '.join(sorted(missing_direct))}")
    version_mismatches = [name for name in direct_names if requirements[name] != direct[name]]
    if version_mismatches:
        raise PackagingError(
            "macOS transitive lock has a direct version mismatch for: "
            + ", ".join(sorted(version_mismatches))
        )
    missing_critical = _CRITICAL_MACOS_TRANSITIVES - locked_names
    if missing_critical:
        raise PackagingError(f"macOS transitive lock is missing critical dependencies: {', '.join(sorted(missing_critical))}")
    return path


def _parse_requirements(lines, *, require_hashes):
    parsed = {}
    for line_number, raw_line in enumerate(lines, 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line != raw_line:
            raise PackagingError(f"unsupported requirement whitespace at line {line_number}")
        if require_hashes:
            match = _REQUIREMENT.fullmatch(line)
        else:
            match = re.fullmatch(
                r"(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)==(?P<version>[^\s;@]+)",
                line,
            )
        if match is None:
            name = line.split("==", 1)[0] if "==" in line else f"line {line_number}"
            malformed_hash = _MALFORMED_HASH_REQUIREMENT.fullmatch(line)
            if malformed_hash:
                raise PackagingError(
                    f"Requirement {malformed_hash.group('name')} has an invalid or missing SHA-256 hash"
                )
            raise PackagingError(f"unsupported requirement syntax at line {line_number}: {line}")
        name = re.sub(r"[-_.]+", "-", match.group("name")).lower()
        if name in parsed:
            raise PackagingError(f"macOS dependency lock contains duplicate package: {name}")
        parsed[name] = match.group("version")
    if not parsed:
        raise PackagingError("Dependency file contains no requirements")
    return parsed
