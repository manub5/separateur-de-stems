"""Fetch the selected model assets into the project-local models directory."""

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from separateur_de_stems.core.bundle_manifest import validate_model_bundle

MODEL_DIR = Path(__file__).resolve().parents[1] / "models"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_CHUNK = 1024 * 1024


class ModelFetchError(RuntimeError):
    """A required asset could not be safely fetched or validated."""


def _valid(path: Path, asset: dict) -> bool:
    if not path.is_file() or path.is_symlink() or path.stat().st_size != asset["size"]:
        return False
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest() == asset["sha256"]


def fetch_asset(model_dir: Path, asset: dict, *, opener=urlopen) -> None:
    """Resume into a .part file, then verify and atomically publish an asset."""
    name = asset.get("path")
    url = asset.get("url")
    size = asset.get("size")
    digest = asset.get("sha256")
    if not isinstance(name, str) or Path(name).name != name or name in ("", ".", ".."):
        raise ModelFetchError(f"Invalid asset path: {name}")
    if not isinstance(url, str) or urlsplit(url).scheme != "https" or not urlsplit(url).netloc:
        raise ModelFetchError(f"Missing or non-HTTPS URL for {name}")
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0 or not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        raise ModelFetchError(f"Invalid size or SHA-256 for {name}")
    root = Path(model_dir)
    if not root.is_dir() or root.is_symlink():
        raise ModelFetchError(f"Model directory is absent or unsafe: {root}")
    dest = root / name
    partial = root / f"{name}.part"
    if dest.is_symlink() or partial.is_symlink():
        raise ModelFetchError(f"Symlink is not allowed for {name}")
    if _valid(dest, asset):
        return
    offset = partial.stat().st_size if partial.is_file() else 0
    if offset >= size:
        partial.unlink()
        offset = 0
    request = Request(url, headers={"Range": f"bytes={offset}-"} if offset else {})
    try:
        with opener(request, timeout=60) as response:
            status = response.status
            if hasattr(response, "geturl") and urlsplit(response.geturl()).scheme != "https":
                raise ModelFetchError(f"Insecure redirect for {name}")
            if offset and status == 206:
                expected = f"bytes {offset}-{size - 1}/{size}"
                if response.headers.get("Content-Range") != expected:
                    raise ModelFetchError(f"Invalid resume range for {name}")
            elif status == 200:
                offset = 0
            else:
                raise ModelFetchError(f"Unexpected HTTP status {status} for {name}")
            with partial.open("ab" if offset else "wb") as stream:
                while chunk := response.read(_CHUNK):
                    stream.write(chunk)
                    if stream.tell() > size:
                        raise ModelFetchError(f"Invalid size for {name}")
    except (HTTPError, URLError, OSError) as error:
        raise ModelFetchError(f"Cannot download {name}: {error}") from error
    if not _valid(partial, asset):
        partial.unlink(missing_ok=True)
        raise ModelFetchError(f"Size or SHA-256 mismatch for {name}")
    os.replace(partial, dest)


def fetch_models(model_dir: Path = MODEL_DIR) -> None:
    root = Path(model_dir)
    root.mkdir(parents=True, exist_ok=True)
    try:
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        assets = manifest["assets"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ModelFetchError(f"Invalid model manifest: {error}") from error
    if not isinstance(assets, list) or not assets:
        raise ModelFetchError("No assets declared in model manifest")
    paths = [item.get("path") for item in assets if isinstance(item, dict)]
    if len(paths) != len(assets) or len(paths) != len(set(paths)) or "download_checks.json" not in paths:
        raise ModelFetchError("Manifest assets must be unique and include download_checks.json")
    for asset in sorted(assets, key=lambda item: item["path"] != "download_checks.json"):
        fetch_asset(root, asset)
    validate_model_bundle(root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        fetch_models()
    except (ModelFetchError, ValueError) as error:
        parser.exit(1, f"Model download failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
