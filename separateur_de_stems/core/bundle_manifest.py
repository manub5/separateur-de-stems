"""Validation for model assets shipped in an offline bundle."""

import hashlib
import json
from pathlib import Path


class BundleManifestError(ValueError):
    pass


def validate_model_bundle(model_dir, *, require_distributable=False):
    root = Path(model_dir)
    manifest_path = root / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BundleManifestError(f"Model manifest is missing or invalid: {error}") from error

    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("models"), list):
        raise BundleManifestError("Model manifest has an unsupported schema")

    assets = []
    for entry in manifest["models"]:
        required = ("filename", "config_files", "sha256", "size", "source", "licence", "licence_status")
        unknown = [field for field in required if entry.get(field) in (None, "", "unknown")]
        if unknown:
            raise BundleManifestError(
                f"Model {entry.get('filename', '<unknown>')} has unknown fields: {', '.join(unknown)}"
            )
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
        for config in entry["config_files"]:
            config_path = _asset_path(root, config)
            _require_file(config_path)
            assets.append(config_path)

    for filename in manifest.get("required_files", []):
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
