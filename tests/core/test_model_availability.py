import hashlib
import json

from separateur_de_stems.core.models import STEM_TO_MODEL, missing_assets_by_stem


def test_missing_assets_by_stem_tracks_shared_model_and_configs(tmp_path):
    payload = b"ready"
    for filename in ("htdemucs_6s.yaml", "six.th"):
        (tmp_path / filename).write_bytes(payload)
    manifest = {
        "models": [
            {"filename": "htdemucs_6s.yaml", "asset_paths": ["htdemucs_6s.yaml", "six.th"]}
        ],
        "assets": [
            {"path": name, "size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
            for name in ("htdemucs_6s.yaml", "six.th")
        ],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))

    missing = missing_assets_by_stem(tmp_path)
    assert "guitar" not in missing
    assert "piano" not in missing
    assert "vocals" in missing
    (tmp_path / "six.th").unlink()
    missing = missing_assets_by_stem(tmp_path)
    assert missing["guitar"] == ("six.th",)
    assert missing["piano"] == ("six.th",)


def test_missing_manifest_disables_every_stem(tmp_path):
    assert set(missing_assets_by_stem(tmp_path)) == set(STEM_TO_MODEL)


def test_malformed_manifest_disables_stems_instead_of_crashing(tmp_path):
    (tmp_path / "manifest.json").write_text(
        json.dumps({"models": [{"filename": "htdemucs_6s.yaml", "asset_paths": [[]]}], "assets": []})
    )
    assert set(missing_assets_by_stem(tmp_path)) == set(STEM_TO_MODEL)
