"""Strict checks shared by PyInstaller and packaging smoke scripts."""

import os
import json
import re
from pathlib import Path

from separateur_de_stems.core.bundle_manifest import BundleManifestError, validate_model_bundle


class PackagingError(RuntimeError):
    pass


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
    except (OSError, json.JSONDecodeError) as error:
        raise PackagingError(f"Redistributed binary licence manifest is invalid: {error}") from error
    entries = manifest.get("binaries") if isinstance(manifest, dict) else None
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1 or not isinstance(entries, list):
        raise PackagingError("Redistributed binary licence manifest has an unsupported schema")
    by_name = {entry.get("name"): entry for entry in entries if isinstance(entry, dict)}
    for name in ("ffmpeg", "ffprobe"):
        entry = by_name.get(name)
        if entry is None:
            raise PackagingError(f"Redistributed binary licence manifest is missing {name}")
        if not isinstance(entry.get("licence"), str) or not entry["licence"]:
            raise PackagingError(f"Redistributed binary {name} has no licence")
        if entry.get("licence_status") != "distributable":
            raise PackagingError(f"Redistributed binary {name} is not distributable")
    return Path(manifest_path)


def validate_macos_release_lock(lock_path):
    path = Path(lock_path)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise PackagingError(f"macOS transitive lock with hashes is absent: {error}") from error
    requirements = [line for line in lines if line.strip() and not line.lstrip().startswith("#")]
    hashes = re.findall(r"--hash=sha256:([0-9a-f]{64})(?:\s|$)", "\n".join(requirements))
    if not requirements or not hashes:
        raise PackagingError("macOS transitive lock with hashes has not been generated and validated")
    return path
