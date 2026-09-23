import hashlib
import json

import pytest

from separateur_de_stems.core.bundle_manifest import (
    BundleManifestError,
    validate_model_bundle,
)
from separateur_de_stems.core.models import STEM_TO_MODEL


def test_repository_manifest_lists_every_selected_model():
    manifest = json.loads(open("models/manifest.json").read())
    assert {entry["filename"] for entry in manifest["models"]} == set(STEM_TO_MODEL.values())
    for entry in manifest["models"]:
        assert {"config_files", "sha256", "size", "source", "licence", "licence_status"} <= entry.keys()


def test_repository_manifest_explicitly_blocks_distribution():
    with pytest.raises(BundleManifestError, match="not distributable|unknown"):
        validate_model_bundle("models", require_distributable=True)


def test_complete_manifest_validates_payload_config_and_check_file(tmp_path):
    payload = tmp_path / "model.ckpt"
    payload.write_bytes(b"payload")
    (tmp_path / "model.yaml").write_text("config")
    (tmp_path / "download_checks.json").write_text("{}")
    manifest = {
        "schema_version": 1,
        "required_files": ["download_checks.json"],
        "models": [{
            "filename": "model.ckpt", "config_files": ["model.yaml"],
            "sha256": hashlib.sha256(b"payload").hexdigest(), "size": 7,
            "source": "https://example.invalid/model", "licence": "MIT",
            "licence_status": "distributable"
        }]
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))

    assert validate_model_bundle(tmp_path, require_distributable=True) == [
        payload, tmp_path / "model.yaml", tmp_path / "download_checks.json", tmp_path / "manifest.json"
    ]


def test_manifest_rejects_checksum_mismatch(tmp_path):
    (tmp_path / "model.ckpt").write_bytes(b"wrong")
    (tmp_path / "download_checks.json").write_text("{}")
    (tmp_path / "manifest.json").write_text(json.dumps({
        "schema_version": 1, "required_files": ["download_checks.json"],
        "models": [{"filename": "model.ckpt", "config_files": [], "sha256": "0" * 64,
                    "size": 5, "source": "source", "licence": "MIT",
                    "licence_status": "distributable"}]
    }))
    with pytest.raises(BundleManifestError, match="SHA-256"):
        validate_model_bundle(tmp_path, require_distributable=True)
