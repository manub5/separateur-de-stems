"""Validation for model assets shipped in an offline bundle."""

import hashlib
import json
import re
from pathlib import Path

from separateur_de_stems.core.models import STEM_TO_MODEL

_SHA256 = re.compile(r"[0-9a-f]{64}")


class PackagingError(ValueError):
    """Invalid or unreadable input required to package a release."""


class BundleManifestError(PackagingError):
    pass


class FrozenBundleError(PackagingError):
    """A frozen application has no usable bundled model set."""


def validate_model_bundle(model_dir, *, require_distributable=False):
    root = Path(model_dir)
    manifest_path = root / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as error:
        raise BundleManifestError(f"Model manifest is not valid UTF-8: {error}") from error
    except (OSError, json.JSONDecodeError) as error:
        raise BundleManifestError(f"Model manifest is missing or invalid: {error}") from error

    if not isinstance(manifest, dict) or set(manifest) != {"schema_version", "models", "assets"}:
        raise BundleManifestError("Model manifest has an unsupported schema")
    if manifest["schema_version"] != 2 or not isinstance(manifest["models"], list) or not isinstance(manifest["assets"], list):
        raise BundleManifestError("Model manifest has an unsupported schema")

    assets_by_path = {}
    for asset in manifest["assets"]:
        if not isinstance(asset, dict) or not {"path", "size", "sha256"} <= set(asset) or set(asset) - {"path", "size", "sha256", "url"}:
            path = asset.get("path", "asset") if isinstance(asset, dict) else "asset"
            raise BundleManifestError(f"Asset {path} must define path, size and sha256")
        path = asset["path"]
        _validate_relative_path(path)
        if path in assets_by_path:
            raise BundleManifestError(f"Model manifest contains duplicate asset path: {path}")
        if not isinstance(asset["size"], int) or isinstance(asset["size"], bool) or asset["size"] <= 0:
            raise BundleManifestError(f"Asset {path} size must be a positive integer")
        if not isinstance(asset["sha256"], str) or not _SHA256.fullmatch(asset["sha256"]):
            raise BundleManifestError(f"Asset {path} sha256 must be 64 lowercase hex characters")
        if "url" in asset and (not isinstance(asset["url"], str) or not asset["url"].startswith("https://")):
            raise BundleManifestError(f"Asset {path} url must be HTTPS")
        assets_by_path[path] = asset
    if "download_checks.json" not in assets_by_path:
        raise BundleManifestError("Asset metadata for download_checks.json is required")

    demucs_weights = _read_demucs_weights(root / "download_checks.json")

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
        asset_paths = entry.get("asset_paths")
        if not isinstance(asset_paths, list) or not asset_paths or not all(isinstance(item, str) and item for item in asset_paths):
            raise BundleManifestError(f"Model {filename} asset_paths must be a non-empty list of strings")
        if len(asset_paths) != len(set(asset_paths)):
            raise BundleManifestError(f"Model {filename} contains duplicate asset paths")
        for path in asset_paths:
            _validate_relative_path(path)
        if filename not in asset_paths:
            raise BundleManifestError(f"Model {filename} must reference its selected model file")
        if filename.endswith(".yaml"):
            expected_weights = demucs_weights.get(filename)
            declared_weights = {path for path in asset_paths if path.endswith(".th")}
            if expected_weights is None or declared_weights != expected_weights:
                raise BundleManifestError(
                    f"cannot determine complete Demucs weights for {filename}"
                )
        for field in ("source", "licence", "licence_status"):
            if not isinstance(entry.get(field), str) or not entry[field]:
                raise BundleManifestError(f"Model {filename} has unknown field: {field}")
        if require_distributable and entry["licence_status"] != "distributable":
            raise BundleManifestError(f"Model {entry['filename']} is not distributable")

    referenced = {"download_checks.json"}
    for entry in manifest["models"]:
        referenced.update(entry["asset_paths"])
    unreferenced = set(assets_by_path) - referenced
    missing_metadata = referenced - set(assets_by_path)
    if unreferenced:
        raise BundleManifestError(f"Manifest assets are not referenced: {', '.join(sorted(unreferenced))}")
    if missing_metadata:
        raise BundleManifestError(f"Referenced assets lack metadata: {', '.join(sorted(missing_metadata))}")

    for filename, metadata in assets_by_path.items():
        required_path = _asset_path(root, filename)
        _require_file(required_path)
        if required_path.stat().st_size != metadata["size"]:
            raise BundleManifestError(f"Size mismatch for {filename}")
        if _sha256(required_path) != metadata["sha256"]:
            raise BundleManifestError(f"SHA-256 mismatch for {filename}")
        assets.append(required_path)
    assets.append(manifest_path)
    return assets


def _read_demucs_weights(download_checks_path: Path) -> dict[str, set[str]]:
    try:
        checks = json.loads(download_checks_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BundleManifestError(
            f"cannot determine complete Demucs weights: invalid download_checks.json: {error}"
        ) from error
    downloads = checks.get("demucs_download_list") if isinstance(checks, dict) else None
    if not isinstance(downloads, dict):
        raise BundleManifestError(
            "cannot determine complete Demucs weights: demucs_download_list is absent"
        )
    result = {}
    for entry in downloads.values():
        if not isinstance(entry, dict) or not all(isinstance(path, str) for path in entry):
            raise BundleManifestError(
                "cannot determine complete Demucs weights: invalid demucs_download_list"
            )
        configs = [path for path in entry if path.endswith(".yaml")]
        weights = {path for path in entry if path.endswith(".th")}
        if len(configs) == 1 and weights:
            if configs[0] in result:
                raise BundleManifestError(
                    f"cannot determine complete Demucs weights for {configs[0]}"
                )
            result[configs[0]] = weights
    return result


def _asset_path(root: Path, filename: str) -> Path:
    candidate = root / filename
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError:
        raise BundleManifestError(f"Manifest asset escapes model directory: {filename}")
    return candidate


def _validate_relative_path(filename) -> None:
    if not isinstance(filename, str) or not filename:
        raise BundleManifestError("Manifest asset path must be a non-empty relative string")
    path = Path(filename)
    if path.is_absolute() or ".." in path.parts:
        raise BundleManifestError(f"Manifest asset path escapes model directory: {filename}")


def _require_file(path: Path) -> None:
    if not path.is_file():
        raise BundleManifestError(f"Required model asset is absent: {path.name}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
