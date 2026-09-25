"""Model downloads must be repeatable, resumable, and confined to models/."""

import hashlib
import io
from pathlib import Path

import pytest

from scripts import fetch_models


class Response(io.BytesIO):
    def __init__(self, data, status, headers=None):
        super().__init__(data)
        self.status = status
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def metadata(content, name="model.ckpt"):
    return {
        "path": name,
        "url": f"https://example.org/{name}",
        "size": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def test_valid_asset_is_not_downloaded(tmp_path):
    (tmp_path / "model.ckpt").write_bytes(b"complete")

    def no_network(request, timeout):
        raise AssertionError("unexpected download")

    fetch_models.fetch_asset(tmp_path, metadata(b"complete"), opener=no_network)


def test_partial_download_resumes_from_confirmed_range(tmp_path):
    (tmp_path / "model.ckpt.part").write_bytes(b"first")

    def opener(request, timeout):
        assert request.get_header("Range") == "bytes=5-"
        return Response(b"second", 206, {"Content-Range": "bytes 5-10/11"})

    fetch_models.fetch_asset(tmp_path, metadata(b"firstsecond"), opener=opener)
    assert (tmp_path / "model.ckpt").read_bytes() == b"firstsecond"
    assert not (tmp_path / "model.ckpt.part").exists()


def test_server_ignoring_range_restarts_safely(tmp_path):
    (tmp_path / "model.ckpt.part").write_bytes(b"old")

    def opener(request, timeout):
        assert request.get_header("Range") == "bytes=3-"
        return Response(b"complete", 200)

    fetch_models.fetch_asset(tmp_path, metadata(b"complete"), opener=opener)
    assert (tmp_path / "model.ckpt").read_bytes() == b"complete"


def test_hash_mismatch_never_publishes_corrupt_asset(tmp_path):
    fetch = lambda request, timeout: Response(b"corrupt", 200)
    with pytest.raises(fetch_models.ModelFetchError, match="SHA-256|taille"):
        fetch_models.fetch_asset(tmp_path, metadata(b"correct"), opener=fetch)
    assert not (tmp_path / "model.ckpt").exists()


@pytest.mark.parametrize("name", ["../escape", "folder/model.ckpt", "/absolute"])
def test_download_cannot_escape_model_directory(tmp_path, name):
    with pytest.raises(fetch_models.ModelFetchError):
        fetch_models.fetch_asset(tmp_path, metadata(b"data", name), opener=None)


def test_download_rejects_missing_url(tmp_path):
    asset = metadata(b"data")
    asset.pop("url")
    with pytest.raises(fetch_models.ModelFetchError, match="URL"):
        fetch_models.fetch_asset(tmp_path, asset)


def test_invalid_existing_file_is_replaced_only_after_verification(tmp_path):
    target = tmp_path / "model.ckpt"
    target.write_bytes(b"old")
    with pytest.raises(fetch_models.ModelFetchError):
        fetch_models.fetch_asset(
            tmp_path, metadata(b"correct"), opener=lambda req, timeout: Response(b"bad", 200)
        )
    assert target.read_bytes() == b"old"


def test_interrupted_transfer_preserves_partial_for_next_run(tmp_path):
    class InterruptedResponse(Response):
        def read(self, size=-1):
            if self.tell():
                raise OSError("connection lost")
            return super().read(3)

    with pytest.raises(fetch_models.ModelFetchError, match="connection lost"):
        fetch_models.fetch_asset(
            tmp_path,
            metadata(b"complete"),
            opener=lambda req, timeout: InterruptedResponse(b"complete", 200),
        )
    assert (tmp_path / "model.ckpt.part").read_bytes() == b"com"


def test_wrong_content_range_does_not_append_to_partial(tmp_path):
    part = tmp_path / "model.ckpt.part"
    part.write_bytes(b"first")
    with pytest.raises(fetch_models.ModelFetchError, match="resume range"):
        fetch_models.fetch_asset(
            tmp_path,
            metadata(b"firstsecond"),
            opener=lambda req, timeout: Response(
                b"second", 206, {"Content-Range": "bytes 0-5/11"}
            ),
        )
    assert part.read_bytes() == b"first"
