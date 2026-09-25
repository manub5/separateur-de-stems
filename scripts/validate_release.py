"""Fail closed until macOS release metadata is complete and verified."""

import argparse
from pathlib import Path

from separateur_de_stems.core.bundle_manifest import validate_model_bundle
from separateur_de_stems.core.packaging import (
    validate_macos_release_lock,
    validate_macos_bundle,
    validate_redistributed_binaries,
    validate_redistributed_binary_licences,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--binary-licences",
        type=Path,
        default=Path("packaging/redistributed-binaries.json"),
    )
    parser.add_argument(
        "--macos-lock",
        type=Path,
        default=Path("requirements/macos-arm64-transitive.lock"),
    )
    parser.add_argument("--ffmpeg", type=Path)
    parser.add_argument("--ffprobe", type=Path)
    parser.add_argument("--platform", choices=("darwin", "linux"))
    parser.add_argument("--binaries-only", action="store_true")
    parser.add_argument("--app", type=Path)
    parser.add_argument("--closure-report", type=Path)
    parser.add_argument("--required-binary", action="append", default=[])
    args = parser.parse_args()
    if args.app is not None:
        validate_macos_bundle(
            args.app,
            report_path=args.closure_report,
            required_binaries=args.required_binary,
        )
    elif args.binaries_only:
        if args.ffmpeg is None or args.ffprobe is None or args.platform is None:
            parser.error("--binaries-only requires --ffmpeg, --ffprobe and --platform")
        validate_redistributed_binaries(
            args.binary_licences,
            {"ffmpeg": args.ffmpeg, "ffprobe": args.ffprobe},
            platform_name=args.platform,
        )
    else:
        validate_redistributed_binary_licences(args.binary_licences)
        validate_macos_release_lock(args.macos_lock, Path("requirements/macos-arm64.lock"))
        validate_model_bundle(Path("models"), require_distributable=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
