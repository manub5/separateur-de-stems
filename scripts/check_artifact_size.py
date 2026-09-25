"""Enforce a conservative project upload policy on the built archive."""

import argparse
from pathlib import Path

MAX_ARTIFACT_BYTES = 2 * 1024**3


def check_artifact_size(archive: Path, *, limit: int = MAX_ARTIFACT_BYTES) -> int:
    size = archive.stat().st_size
    if size > limit:
        raise ValueError(
            f"Artifact too large: {size} bytes exceeds project limit {limit}; "
            "reduce bundle size or choose a separately validated delivery method"
        )
    return size


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    try:
        size = check_artifact_size(args.archive)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Artifact size check failed: {error}\n")
    print(f"Archive size: {size} bytes (limit {MAX_ARTIFACT_BYTES})")


if __name__ == "__main__":
    main()
