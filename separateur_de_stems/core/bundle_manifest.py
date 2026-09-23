"""Validation for model assets shipped in an offline bundle."""

import hashlib
import json
import re
from pathlib import Path

from separateur_de_stems.core.models import STEM_TO_MODEL

_SHA256 = re.compile(r"[0-9a-f]{64}")


class BundleManifestError(ValueError):
    pass


def validate_model_bundle(model_dir, *, require_distributable=False):
    root = Path(model_dir)
    manifest_path = root / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BundleManifestError(f"Model manifest is missing or invalid: {error}") from error

    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1 or not isinstance(manifest.get("models"), list):
        raise BundleManifestError("Model manifest has an unsupported schema")

    required_files = manifest.get("required_files")
    if not isinstance(required_files, list) or not all(isinstance(item, str) and item for item in required_files):
        raise BundleManifestError("required_files must be a list of non-empty strings")
    if "download_checks.json" not in required_files:
        raise BundleManifestError("required_files must contain download_checks.json")

    if not all(isinstance(entry, dict) for entry in manifest["models"]):
        raise BundleManifestError("models must contain objects")
    filenames = [entry.get("filename") for entry in manifest["models"]]
    if not all(isinstance(filename, str) and filename for filename in filenames):
        raise BundleManifestError("Model filename must be a non-empty string")
    if len(filenames) != len(set(filenames)):
        raise BundleManifestError("Model manifest contains duplicate filenames")
    if set(filenames) != set(STEM_TO_MODEL.values()):
        raise BundleManifestError("Model manifest must exactly match selected models")

    assets = []
    for entry in manifest["models"]:
        filename = entry["filename"]
        config_files = entry.get("config_files")
        if not isinstance(config_files, list) or not all(isinstance(item, str) and item for item in config_files):
            raise BundleManifestError(f"Model {filename} config_files must be a list of strings")
        if not isinstance(entry.get("sha256"), str) or not _SHA256.fullmatch(entry["sha256"]):
            raise BundleManifestError(f"Model {filename} sha256 must be 64 lowercase hex characters")
        if not isinstance(entry.get("size"), int) or isinstance(entry["size"], bool) or entry["size"] <= 0:
            raise BundleManifestError(f"Model {filename} size must be a positive integer")
        for field in ("source", "licence", "licence_status"):
            if not isinstance(entry.get(field), str) or not entry[field]:
                raise BundleManifestError(f"Model {filename} has unknown field: {field}")
        if require_distributable and entry["licence_status"] != "distributable":
            raise BundleManifestError(f"Model {entry['filename']} is not distributable")

        payload = _asset_path(root, entry["filename"])
        _require_file(payload)
        if payload.stat().st_size != entry["size"]:
            raise BundleManifestError(f"Size mismatch for {entry['filename']}")
        digest = _sha256(payload)
        if digest != entry["sha256"]:
            raise BundleManifestError(f"SHA-256 mismatch for {entry['filename']}")
        assets.append(payload)
        for config in config_files:
            config_path = _asset_path(root, config)
            _require_file(config_path)
            assets.append(config_path)

    for filename in required_files:
        required_path = _asset_path(root, filename)
        _require_file(required_path)
        assets.append(required_path)
    assets.append(manifest_path)
    return assets


def _asset_path(root: Path, filename: str) -> Path:
    candidate = root / filename
    if candidate.parent.resolve() != root.resolve():
        raise BundleManifestError(f"Manifest asset escapes model directory: {filename}")
    return candidate


def _require_file(path: Path) -> None:
    if not path.is_file():
        raise BundleManifestError(f"Required model asset is absent: {path.name}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
