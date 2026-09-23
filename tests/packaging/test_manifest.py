import hashlib
import json

import pytest

from separateur_de_stems.core.bundle_manifest import BundleManifestError, validate_model_bundle
from separateur_de_stems.core.models import STEM_TO_MODEL
from separateur_de_stems.core.packaging import PackagingError


def _entry(filename, payload=b"payload", **overrides):
    entry = {
        "filename": filename,
        "config_files": [],
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size": len(payload),
        "source": "https://example.invalid/model",
        "licence": "MIT",
        "licence_status": "distributable",
    }
    entry.update(overrides)
    return entry


def _write_complete_bundle(root, *, mutate=None):
    entries = []
    for filename in sorted(set(STEM_TO_MODEL.values())):
        payload = filename.encode()
        (root / filename).write_bytes(payload)
        entries.append(_entry(filename, payload))
    (root / "download_checks.json").write_text("{}")
    manifest = {
        "schema_version": 1,
        "required_files": ["download_checks.json"],
        "models": entries,
    }
    if mutate:
        mutate(manifest)
    (root / "manifest.json").write_text(json.dumps(manifest))
    return manifest


def test_repository_manifest_explicitly_blocks_distribution():
    with pytest.raises(BundleManifestError, match="sha256|unknown"):
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


def test_manifest_requires_download_checks_declaration(tmp_path):
    _write_complete_bundle(tmp_path, mutate=lambda data: data["required_files"].clear())
    with pytest.raises(BundleManifestError, match="download_checks.json"):
        validate_model_bundle(tmp_path)


@pytest.mark.parametrize(
    ("field", "value"),
    [("config_files", None), ("sha256", "bad"), ("size", 0), ("size", "7")],
)
def test_manifest_rejects_invalid_model_field_types(tmp_path, field, value):
    def mutate(data):
        data["models"][0][field] = value

    _write_complete_bundle(tmp_path, mutate=mutate)
    with pytest.raises(BundleManifestError, match=field):
        validate_model_bundle(tmp_path)


def test_manifest_rejects_non_string_config_or_required_file(tmp_path):
    _write_complete_bundle(
        tmp_path,
        mutate=lambda data: data["models"][0].update(config_files=[1]),
    )
    with pytest.raises(BundleManifestError, match="config_files"):
        validate_model_bundle(tmp_path)

    _write_complete_bundle(
        tmp_path,
        mutate=lambda data: data.update(required_files=["download_checks.json", 1]),
    )
    with pytest.raises(BundleManifestError, match="required_files"):
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
