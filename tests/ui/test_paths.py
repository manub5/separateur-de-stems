"""Tests for development and frozen path resolution.

The frozen (PyInstaller) branches cannot be exercised for real on Linux;
they are emulated by monkeypatching ``sys.frozen`` and ``sys._MEIPASS``.
Qt is run in offscreen mode.
"""

import sys
import json

import pytest

from separateur_de_stems.core.bundle_manifest import FrozenBundleError
from separateur_de_stems.core.models import STEM_TO_MODEL
from separateur_de_stems.ui import paths


@pytest.fixture(autouse=True)
def clean_frozen(monkeypatch):
    """Ensure sys.frozen / sys._MEIPASS are absent unless a test sets them."""
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    yield


def test_is_frozen_false_in_dev():
    assert paths.is_frozen() is False


def test_is_frozen_true_when_sys_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert paths.is_frozen() is True


def test_default_model_dir_dev():
    assert paths.default_model_dir() == "models"


def test_default_cache_dir_dev():
    assert paths.default_cache_dir() == ".cache"


def test_default_model_dir_frozen_without_valid_manifest_stays_explicit(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", "/missing-bundle", raising=False)
    with pytest.raises(FrozenBundleError, match="bundled models"):
        paths.default_model_dir()


def test_default_model_dir_frozen_uses_complete_bundle(monkeypatch, tmp_path):
    models = tmp_path / "models"
    models.mkdir()
    import hashlib
    entries = []
    for filename in sorted(set(STEM_TO_MODEL.values())):
        payload = filename.encode()
        (models / filename).write_bytes(payload)
        asset_paths = [filename]
        if filename.endswith(".yaml"):
            weight = f"{filename}.th"
            (models / weight).write_bytes(weight.encode())
            asset_paths.append(weight)
        entries.append({
            "filename": filename, "asset_paths": asset_paths,
            "source": "https://example.invalid/model", "licence": "MIT",
            "licence_status": "distributable"
        })
    checks = b"{}"
    assets = []
    for entry in entries:
        for asset_path in entry["asset_paths"]:
            payload = (models / asset_path).read_bytes()
            assets.append({"path": asset_path, "sha256": hashlib.sha256(payload).hexdigest(), "size": len(payload)})
    assets.append({"path": "download_checks.json", "sha256": hashlib.sha256(checks).hexdigest(), "size": len(checks)})
    manifest = {
        "schema_version": 2,
        "models": entries,
        "assets": assets,
    }
    (models / "download_checks.json").write_bytes(checks)
    (models / "manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert paths.default_model_dir() == str(models)


def test_default_cache_dir_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    result = paths.default_cache_dir()
    assert result.endswith("cache")
    assert "StemSeparator" in result


def test_default_output_dir_non_empty():
    result = paths.default_output_dir()
    assert isinstance(result, str)
    assert result
