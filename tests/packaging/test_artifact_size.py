import pytest

from scripts.check_artifact_size import MAX_ARTIFACT_BYTES, check_artifact_size


def test_archive_size_under_policy_limit(tmp_path):
    archive = tmp_path / "app.zip"
    archive.write_bytes(b"hello")
    assert check_artifact_size(archive, limit=6) == 5


def test_archive_over_policy_limit_fails_before_upload(tmp_path):
    archive = tmp_path / "app.zip"
    archive.write_bytes(b"overflow")
    with pytest.raises(ValueError, match="too large"):
        check_artifact_size(archive, limit=6)


def test_default_limit_is_conservative_policy():
    assert MAX_ARTIFACT_BYTES == 2 * 1024**3
