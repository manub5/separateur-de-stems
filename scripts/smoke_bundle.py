"""Inspect a frozen bundle and verify its private ffmpeg without system PATH."""

import argparse
import os
import subprocess
import tempfile
import wave
from pathlib import Path

from separateur_de_stems.core.packaging import PackagingError, validate_build_inputs


def smoke_ffmpeg(ffmpeg: Path, work_dir: Path) -> None:
    source = work_dir / "synthetic.wav"
    target = work_dir / "synthetic.mp3"
    with wave.open(str(source), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\0\0" * 800)
    env = dict(os.environ)
    env["PATH"] = ""
    subprocess.run(
        [str(ffmpeg), "-nostdin", "-y", "-i", str(source), "-b:a", "320k", target],
        check=True,
        capture_output=True,
        env=env,
    )
    if not target.is_file() or target.stat().st_size == 0:
        raise PackagingError("Bundled ffmpeg did not produce an MP3")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle_root", type=Path)
    args = parser.parse_args()
    root = args.bundle_root
    ffmpeg_dir = root / "ffmpeg"
    assets = validate_build_inputs(
        root / "models", root / "separateur_de_stems" / "ui" / "i18n",
        ffmpeg_dir / "ffmpeg", ffmpeg_dir / "ffprobe",
        ffmpeg_dir / "redistributed-binaries.json",
    )
    with tempfile.TemporaryDirectory() as directory:
        smoke_ffmpeg(ffmpeg_dir / "ffmpeg", Path(directory))
    print(f"Validated {len(assets)} offline model assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
