"""Audio export helpers: 24-bit WAV rewriting and 320 kb/s MP3 encoding."""

import subprocess
import tempfile
import time
from pathlib import Path

import soundfile as sf

from separateur_de_stems.core.errors import CancelledError, OutputError
from separateur_de_stems.core.platform import ffmpeg_executable

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


def to_mp3_320(src: str, dest: str, cancel_requested=None) -> str:
    _ensure_parent(dest)
    target = Path(dest)
    preexisting = target.exists()

    ffmpeg = ffmpeg_executable()
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
        if cancel_requested is None:
            subprocess.run(args, capture_output=True, check=True)
        else:
            _run_cancellable(args, cancel_requested)
    except CancelledError:
        _cleanup_partial(target, preexisting)
        raise
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


def _run_cancellable(args: list[str], cancel_requested) -> None:
    with tempfile.TemporaryFile() as stderr_file:
        process = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=stderr_file,
        )
        while process.poll() is None:
            if cancel_requested():
                process.terminate()
                try:
                    process.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                raise CancelledError("MP3 encoding cancelled")
            time.sleep(0.05)
        if process.returncode:
            stderr_file.flush()
            size = stderr_file.seek(0, 2)
            stderr_file.seek(max(0, size - _STDERR_TAIL))
            stderr = stderr_file.read()
            raise subprocess.CalledProcessError(
                process.returncode, args, stderr=stderr
            )
