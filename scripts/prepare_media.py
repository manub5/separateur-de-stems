"""Record the actual macOS ffmpeg/ffprobe binaries installed by Homebrew."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from separateur_de_stems.core.bundle_manifest import PackagingError
from separateur_de_stems.core.packaging import _parse_binary_version


def _inspect(command):
    try:
        return subprocess.run(
            [str(part) for part in command], check=True, capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        raise PackagingError(f"Cannot inspect media tool: {error}") from error


def generate_binary_manifest(paths, formula, *, inspect=_inspect, output_path):
    """Bind provenance and SHA-256 to the bytes actually installed on macOS."""
    if (
        formula.get("name") != "ffmpeg"
        or formula.get("license") != "GPL-3.0-or-later"
        or not {"x264", "x265"} <= set(formula.get("dependencies", []))
    ):
        raise PackagingError("Homebrew ffmpeg GPL / x264 / x265 metadata has changed")
    try:
        version = formula["versions"]["stable"]
        source = formula["urls"]["stable"]["url"]
    except (KeyError, TypeError) as error:
        raise PackagingError(f"Homebrew ffmpeg source or version is absent: {error}") from error
    if not isinstance(version, str) or not version or not isinstance(source, str) or not source.startswith("https://"):
        raise PackagingError("Homebrew ffmpeg source or version is invalid")
    entries = []
    for name in ("ffmpeg", "ffprobe"):
        path = Path(paths[name])
        if not path.is_file() or path.is_symlink() or path.stat().st_size == 0:
            raise PackagingError(f"Missing or unsafe {name}: {path}")
        actual = _parse_binary_version(inspect([path, "-version"]), name)
        if actual != version:
            raise PackagingError(f"{name} version {actual} differs from Homebrew formula {version}")
        if "arm64" not in inspect(["file", "-b", path]):
            raise PackagingError(f"{name} is not arm64")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        entries.append({
            "name": name, "licence": formula["license"], "source": source,
            "version": actual, "architecture": "arm64", "sha256": digest.hexdigest(),
            "dependency_policy": "system-only", "licence_status": "not-distributable",
        })
    result = {"schema_version": 1, "binaries": entries}
    Path(output_path).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("packaging/redistributed-binaries.json"))
    args = parser.parse_args()
    try:
        formula = json.loads(_inspect(["brew", "info", "--json=v2", "ffmpeg"]))["formulae"][0]
        paths = {name: Path(_inspect(["which", name]).strip()).resolve() for name in ("ffmpeg", "ffprobe")}
        generate_binary_manifest(paths, formula, output_path=args.output)
    except (PackagingError, OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        parser.exit(1, f"Media preparation failed: {error}\n")


if __name__ == "__main__":
    main()
