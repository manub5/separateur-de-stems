"""Transactional separation, export, publication, and workspace cleanup."""

import ctypes
import errno
import os
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

from separateur_de_stems.core.engine import SeparationEngine
from separateur_de_stems.core.errors import CancelledError, OutputError
from separateur_de_stems.core.export import to_mp3_320, to_wav24
from separateur_de_stems.core.naming import sanitize, stem_filename

_SEPARATION_PROGRESS_MAX = 80


def run_pipeline(
    input_path,
    stems,
    output_dir,
    model_dir,
    *,
    include_mp3=True,
    progress_cb=None,
    cancel_requested=None,
    _workspace=None,
) -> dict[str, list[str]]:
    """Run a complete separation and publish only a complete result."""
    requested = frozenset(stems)
    output = Path(output_dir)
    workspace = Path(_workspace) if _workspace else None
    if workspace is not None:
        try:
            is_private = (
                workspace.resolve().parent == output.resolve()
                and workspace.name.startswith(".stem-separator-")
            )
        except OSError:
            is_private = False
        if not is_private:
            raise OutputError("Private workspace must be a run directory under output")
    try:
        output.mkdir(parents=True, exist_ok=True)
        workspace = workspace or Path(
            tempfile.mkdtemp(prefix=".stem-run-", dir=str(output))
        )
        workspace.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise OutputError(f"Cannot create private workspace: {error}") from error

    context = SimpleNamespace(
        input_path=str(input_path),
        output_dir=str(output),
        model_dir=str(model_dir),
        stems=requested,
        workspace=str(workspace),
    )
    cancelled = cancel_requested or (lambda: False)

    def separation_progress(percent, stage):
        _report(progress_cb, min(_SEPARATION_PROGRESS_MAX, int(percent * 0.8)), stage)

    try:
        _raise_if_cancelled(cancelled)
        engine = SeparationEngine(str(model_dir), str(workspace))
        outputs = engine.run(
            str(input_path), set(requested), progress_cb=separation_progress
        )
        missing = requested - outputs.keys()
        if missing:
            raise OutputError(
                f"Requested stem(s) missing from result: {', '.join(sorted(missing))}"
            )
        paths = _finalize_outputs(
            context,
            outputs,
            include_mp3=include_mp3,
            cancel_requested=cancelled,
            progress_cb=progress_cb,
        )
        result = {
            stem: [path for path in paths if f"_{sanitize(stem)}." in Path(path).name]
            for stem in requested
        }
        incomplete = [stem for stem, files in result.items() if not files]
        if incomplete:
            raise OutputError(
                f"No deliverable produced for: {', '.join(sorted(incomplete))}"
            )
        _notify_completion(progress_cb)
        return result
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def _finalize_outputs(
    context,
    outputs,
    wav_exporter=None,
    mp3_exporter=None,
    cancel_requested=lambda: False,
    include_mp3=True,
    progress_cb=None,
    rename_publisher=None,
) -> list[str]:
    """Stage every deliverable, then atomically publish the complete song."""
    if not outputs:
        raise OutputError("Separation returned no outputs")
    missing = context.stems - outputs.keys()
    if missing:
        raise OutputError(f"Missing outputs: {', '.join(sorted(missing))}")

    workspace = Path(context.workspace).resolve()
    sources = {stem: Path(outputs[stem]) for stem in context.stems}
    for stem, source in sources.items():
        try:
            resolved = source.resolve(strict=True)
            resolved.relative_to(workspace)
        except (OSError, ValueError) as error:
            raise OutputError(
                f"Model output for {stem} is outside the private workspace: {source}"
            ) from error
        if not resolved.is_file():
            raise OutputError(f"Model output is not a file: {source}")

    wav_exporter = wav_exporter or to_wav24
    mp3_exporter = mp3_exporter or to_mp3_320
    song = sanitize(Path(context.input_path).stem)
    final_song_dir = Path(context.output_dir) / song
    staged_song_dir = workspace / f".{song}.staging"
    exported = []
    formats_per_stem = 2 if include_mp3 else 1
    total = len(context.stems) * formats_per_stem
    completed = 0

    for stem in sorted(context.stems):
        _raise_if_cancelled(cancel_requested)
        wav_path = Path(
            stem_filename(context.input_path, stem, "wav", str(staged_song_dir))
        )
        wav_exporter(str(sources[stem]), str(wav_path))
        exported.append(wav_path)
        completed += 1
        _report_export(progress_cb, completed, total, "export.wav")
        _raise_if_cancelled(cancel_requested)
        if include_mp3:
            mp3_path = Path(
                stem_filename(context.input_path, stem, "mp3", str(staged_song_dir))
            )
            mp3_exporter(
                str(wav_path), str(mp3_path), cancel_requested=cancel_requested
            )
            exported.append(mp3_path)
            completed += 1
            _report_export(progress_cb, completed, total, "export.mp3")
            _raise_if_cancelled(cancel_requested)

    missing_deliverables = [path for path in exported if not path.is_file()]
    if missing_deliverables:
        raise OutputError(f"Export did not create: {missing_deliverables[0]}")
    _raise_if_cancelled(cancel_requested)
    try:
        (rename_publisher or _rename_no_replace)(staged_song_dir, final_song_dir)
    except OSError as error:
        raise OutputError(
            f"Failed to publish completed outputs to {final_song_dir}: {error}"
        ) from error
    return [str(final_song_dir / path.name) for path in exported]


def _report_export(progress_cb, completed, total, stage):
    percent = _SEPARATION_PROGRESS_MAX + int(completed * 19 / total)
    _report(progress_cb, percent, stage)


def _report(progress_cb, percent, stage):
    if progress_cb is not None:
        progress_cb(percent, stage)


def _notify_completion(progress_cb):
    """Notify observers after commit without invalidating published success."""
    try:
        _report(progress_cb, 100, "pipeline.complete")
    except Exception:  # noqa: BLE001
        pass


def _raise_if_cancelled(cancel_requested):
    if cancel_requested():
        raise CancelledError("Pipeline cancelled")


def _rename_no_replace(source: Path, destination: Path) -> None:
    """Atomically rename without replacement, or fail closed."""
    libc = ctypes.CDLL(None, use_errno=True)
    source_bytes = os.fsencode(source)
    destination_bytes = os.fsencode(destination)
    if sys.platform.startswith("linux"):
        rename = getattr(libc, "renameat2", None)
        if rename is None:
            raise OSError(errno.ENOTSUP, "renameat2 is unavailable")
        rename.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename.restype = ctypes.c_int
        result = rename(-100, source_bytes, -100, destination_bytes, 1)
    elif sys.platform == "darwin":
        rename = getattr(libc, "renamex_np", None)
        if rename is None:
            raise OSError(errno.ENOTSUP, "renamex_np is unavailable")
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(source_bytes, destination_bytes, 4)
    else:
        raise OSError(errno.ENOTSUP, "atomic no-replace rename is unavailable")
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number in (errno.EEXIST, errno.ENOTEMPTY):
        raise FileExistsError(
            error_number,
            f"Output already exists: {destination}",
            str(destination),
        )
    raise OSError(error_number, os.strerror(error_number), str(destination))
