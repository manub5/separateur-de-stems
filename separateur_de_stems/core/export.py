"""Audio export helpers: 24-bit WAV rewriting and 320 kb/s MP3 encoding."""

import subprocess
from pathlib import Path
from shutil import which

import soundfile as sf

from separateur_de_stems.core.errors import OutputError

_MP3_BITRATE = "320k"
_STDERR_TAIL = 400


def _ensure_parent(dest: str) -> Path:
    target = Path(dest)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise OutputError(
            f"Cannot create output directory {target.parent}: {error}"
        ) from error
    return target


def _cleanup_partial(target: Path, preexisting: bool) -> None:
    if preexisting:
        return
    try:
        if target.exists():
            target.unlink()
    except OSError:
        pass


def to_wav24(src: str, dest: str) -> str:
    target = _ensure_parent(dest)
    preexisting = target.exists()
    try:
        data, sample_rate = sf.read(src, always_2d=True)
        sf.write(str(target), data, sample_rate, subtype="PCM_24")
    except OutputError:
        raise
    except Exception as error:  # noqa: BLE001
        _cleanup_partial(target, preexisting)
        raise OutputError(f"Failed to write 24-bit WAV {dest}: {error}") from error
    return dest


def to_mp3_320(src: str, dest: str) -> str:
    _ensure_parent(dest)
    target = Path(dest)
    preexisting = target.exists()

    ffmpeg = which("ffmpeg") or "ffmpeg"
    args = [
        ffmpeg,
        "-y",
        "-i",
        src,
        "-b:a",
        _MP3_BITRATE,
        str(target),
    ]

    try:
        subprocess.run(args, capture_output=True, check=True)
    except Exception as error:  # noqa: BLE001
        _cleanup_partial(target, preexisting)
        detail = ""
        stderr = getattr(error, "stderr", None)
        if stderr:
            if isinstance(stderr, bytes):
                stderr = stderr.decode(errors="replace")
            detail = f": {stderr[-_STDERR_TAIL:]}"
        raise OutputError(f"Failed to encode MP3 {dest}{detail}") from error
    return dest
