import hashlib
import json

import pytest

from separateur_de_stems.core.bundle_manifest import BundleManifestError, validate_model_bundle
from separateur_de_stems.core.models import STEM_TO_MODEL
from separateur_de_stems.core.packaging import PackagingError


def _entry(filename, payload=b"payload", **overrides):
    entry = {
        "filename": filename,
        "asset_paths": [filename],
        "source": "https://example.invalid/model",
        "licence": "MIT",
        "licence_status": "distributable",
    }
    entry.update(overrides)
    return entry


def _asset(path, payload):
    return {
        "path": path,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size": len(payload),
    }


def _write_complete_bundle(root, *, mutate=None):
    entries = []
    for filename in sorted(set(STEM_TO_MODEL.values())):
        payload = filename.encode()
        (root / filename).write_bytes(payload)
        entry = _entry(filename, payload)
        if filename.endswith(".yaml"):
            weight = f"{filename.removesuffix('.yaml')}.th"
            weight_payload = weight.encode()
            (root / weight).write_bytes(weight_payload)
            entry["asset_paths"].append(weight)
        entries.append(entry)
    demucs_downloads = {}
    for entry in entries:
        if entry["filename"].endswith(".yaml"):
            demucs_downloads[f"Demucs v4: {entry['filename'][:-5]}"] = {
                path.rsplit("/", 1)[-1]: f"https://example.invalid/{path}"
                for path in entry["asset_paths"]
            }
    checks = json.dumps({"demucs_download_list": demucs_downloads}).encode()
    (root / "download_checks.json").write_bytes(checks)
    assets = [_asset("download_checks.json", checks)]
    for entry in entries:
        for path in entry["asset_paths"]:
            assets.append(_asset(path, (root / path).read_bytes()))
    manifest = {
        "schema_version": 2,
        "assets": assets,
        "models": entries,
    }
    if mutate:
        mutate(manifest)
    (root / "manifest.json").write_text(json.dumps(manifest))
    return manifest


def test_repository_manifest_blocks_on_unknown_asset_metadata():
    with pytest.raises(BundleManifestError, match=r"download_checks\.json size"):
        validate_model_bundle("models", require_distributable=True)


def test_model_manifest_invalid_utf8_is_contextual_packaging_error(tmp_path):
    (tmp_path / "manifest.json").write_bytes(b"\xff")
    with pytest.raises(PackagingError, match="Model manifest.*UTF-8"):
        validate_model_bundle(tmp_path)


def test_complete_manifest_validates_every_selected_model(tmp_path):
    _write_complete_bundle(tmp_path)
    assets = validate_model_bundle(tmp_path, require_distributable=True)
    assert {path.name for path in assets} >= set(STEM_TO_MODEL.values())


def test_manifest_rejects_partial_selected_model_set(tmp_path):
    _write_complete_bundle(tmp_path, mutate=lambda data: data["models"].pop())
    with pytest.raises(BundleManifestError, match="selected models"):
        validate_model_bundle(tmp_path)


def test_manifest_requires_hashed_download_checks_asset(tmp_path):
    _write_complete_bundle(
        tmp_path,
        mutate=lambda data: data["assets"].__setitem__(0, {"path": "download_checks.json", "size": 2}),
    )
    with pytest.raises(BundleManifestError, match="download_checks.json"):
        validate_model_bundle(tmp_path)


@pytest.mark.parametrize(
    ("field", "value"),
    [("asset_paths", None), ("source", None), ("licence", None)],
)
def test_manifest_rejects_invalid_model_field_types(tmp_path, field, value):
    def mutate(data):
        data["models"][0][field] = value

    _write_complete_bundle(tmp_path, mutate=mutate)
    with pytest.raises(BundleManifestError, match=field):
        validate_model_bundle(tmp_path)


def test_manifest_rejects_non_string_asset_reference(tmp_path):
    _write_complete_bundle(
        tmp_path,
        mutate=lambda data: data["models"][0].update(asset_paths=[1]),
    )
    with pytest.raises(BundleManifestError, match="asset_paths"):
        validate_model_bundle(tmp_path)


def test_manifest_rejects_missing_declared_asset(tmp_path):
    manifest = _write_complete_bundle(tmp_path)
    missing = manifest["assets"][-1]["path"]
    (tmp_path / missing).unlink()
    with pytest.raises(BundleManifestError, match="absent"):
        validate_model_bundle(tmp_path)


def test_manifest_rejects_uninventoried_demucs_weight(tmp_path):
    def mutate(data):
        demucs = next(entry for entry in data["models"] if entry["filename"].endswith(".yaml"))
        demucs["asset_paths"] = [demucs["filename"]]

    _write_complete_bundle(tmp_path, mutate=mutate)
    with pytest.raises(BundleManifestError, match="complete Demucs weights"):
        validate_model_bundle(tmp_path)


def test_manifest_rejects_arbitrary_demucs_weight(tmp_path):
    def mutate(data):
        demucs = next(entry for entry in data["models"] if entry["filename"].endswith(".yaml"))
        expected = next(path for path in demucs["asset_paths"] if path.endswith(".th"))
        demucs["asset_paths"].remove(expected)
        demucs["asset_paths"].append("weights/arbitrary.th")
        data["assets"] = [asset for asset in data["assets"] if asset["path"] != expected]
        payload = b"arbitrary"
        (tmp_path / "weights").mkdir(exist_ok=True)
        (tmp_path / "weights" / "arbitrary.th").write_bytes(payload)
        data["assets"].append(_asset("weights/arbitrary.th", payload))

    _write_complete_bundle(tmp_path, mutate=mutate)
    with pytest.raises(BundleManifestError, match="complete Demucs weights"):
        validate_model_bundle(tmp_path)


def test_manifest_rejects_missing_exact_demucs_weight(tmp_path):
    def mutate(data):
        demucs = next(entry for entry in data["models"] if entry["filename"].endswith(".yaml"))
        expected = next(path for path in demucs["asset_paths"] if path.endswith(".th"))
        demucs["asset_paths"].remove(expected)
        data["assets"] = [asset for asset in data["assets"] if asset["path"] != expected]

    _write_complete_bundle(tmp_path, mutate=mutate)
    with pytest.raises(BundleManifestError, match="complete Demucs weights"):
        validate_model_bundle(tmp_path)


@pytest.mark.parametrize("path", ["../escape", "/absolute", "nested/../../escape"])
def test_manifest_rejects_asset_path_traversal(tmp_path, path):
    _write_complete_bundle(
        tmp_path,
        mutate=lambda data: data["assets"][0].update(path=path),
    )
    with pytest.raises(BundleManifestError, match="escapes|relative"):
        validate_model_bundle(tmp_path)


def test_manifest_rejects_duplicate_asset_paths(tmp_path):
    _write_complete_bundle(
        tmp_path,
        mutate=lambda data: data["assets"].append(dict(data["assets"][0])),
    )
    with pytest.raises(BundleManifestError, match="duplicate asset"):
        validate_model_bundle(tmp_path)


def test_manifest_rejects_duplicate_models(tmp_path):
    _write_complete_bundle(
        tmp_path,
        mutate=lambda data: data["models"].append(dict(data["models"][0])),
    )
    with pytest.raises(BundleManifestError, match="duplicate"):
        validate_model_bundle(tmp_path)


def test_manifest_rejects_non_string_filename_as_schema_error(tmp_path):
    _write_complete_bundle(
        tmp_path,
        mutate=lambda data: data["models"][0].update(filename=[]),
    )
    with pytest.raises(BundleManifestError, match="filename"):
        validate_model_bundle(tmp_path)
