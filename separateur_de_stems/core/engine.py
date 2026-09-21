"""Separation engine orchestrating audio-separator models for the CLI."""

import logging
import os
from pathlib import Path
from typing import Callable, Optional

from separateur_de_stems.core.errors import (
    CancelledError,
    ModelUnavailableError,
    OutputError,
    StemSeparatorError,
    UnsupportedFormatError,
)
from separateur_de_stems.core.models import (
    STEM_TO_MODEL,
    SUPPORTED_EXTENSIONS,
    select_models,
)


def _lazy_separator_factory(**kwargs):
    from audio_separator.separator import Separator

    return Separator(**kwargs)


class SeparationEngine:
    """Run audio separation for a set of requested stems."""

    def __init__(
        self,
        model_dir: str,
        output_dir: str,
        log_level: int = logging.INFO,
        separator_factory=None,
    ):
        self._model_dir = model_dir
        self._output_dir = output_dir
        self._log_level = log_level
        self._separator_factory = separator_factory or _lazy_separator_factory

    def run(
        self,
        input_path: str,
        stems: set[str],
        progress_cb: Optional[Callable[[int, str], None]] = None,
        cancel_event=None,
    ) -> dict[str, str]:
        self._check_cancelled(cancel_event)

        if not stems:
            raise ModelUnavailableError("No stems requested")

        source = Path(input_path)
        if not source.is_file():
            raise UnsupportedFormatError(f"Input file not found: {input_path}")

        if source.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise UnsupportedFormatError(
                f"Unsupported input format: {source.suffix}"
            )

        models = select_models(stems)
        self._prepare_output_dir()

        self._report(progress_cb, 0, "Starting separation")

        collected: dict[str, str] = {}
        total = len(models)
        for index, model in enumerate(models):
            self._check_cancelled(cancel_event)
            start = int(index * 90 / total)
            self._report(progress_cb, start, f"Loading model {model.filename}")

            separator = self._separator_factory(
                model_file_dir=self._model_dir,
                output_dir=self._output_dir,
                output_format="WAV",
                log_level=self._log_level,
            )
            separator.load_model(model.filename)

            self._report(
                progress_cb,
                int((index + 0.5) * 90 / total),
                f"Separating model {model.filename}",
            )
            outputs = self._separate(separator, input_path, model.filename)
            self._collect(outputs, stems, collected, model.filename)

            self._check_cancelled(cancel_event)
            end = int((index + 1) * 90 / total)
            self._report(progress_cb, end, f"Finished model {model.filename}")

        missing = sorted(stems - collected.keys())
        if missing:
            raise OutputError(
                f"Requested stem(s) not found in model outputs: {', '.join(missing)}"
            )

        self._report(progress_cb, 100, "Separation complete")
        return collected

    def _prepare_output_dir(self) -> None:
        directory = Path(self._output_dir)
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise OutputError(
                f"Cannot create output directory {self._output_dir}: {error}"
            ) from error

        if not directory.is_dir():
            raise OutputError(f"Output path is not a directory: {self._output_dir}")
        if not os.access(directory, os.W_OK | os.X_OK):
            raise OutputError(
                f"Output directory is not writable: {self._output_dir}"
            )

    def _separate(self, separator, input_path: str, filename: str):
        try:
            return separator.separate(input_path)
        except StemSeparatorError:
            raise
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as error:  # noqa: BLE001
            from audio_separator.separator import (
                AudioExportError,
                BatchSeparationError,
                InvalidAudioDataError,
            )

            if isinstance(error, InvalidAudioDataError):
                raise UnsupportedFormatError(str(error)) from error
            if isinstance(error, (AudioExportError, BatchSeparationError)):
                raise OutputError(str(error)) from error
            raise OutputError(
                f"Separation failed for {Path(input_path).name} "
                f"with model {filename}: {error}"
            ) from error

    def _collect(
        self,
        outputs,
        stems: set[str],
        collected: dict[str, str],
        model_filename: str,
    ) -> None:
        for output in outputs:
            stem = self._stem_from_output(output)
            if stem is None:
                continue
            if stem not in stems or stem in collected:
                continue
            if STEM_TO_MODEL.get(stem) != model_filename:
                continue
            collected[stem] = self._resolve_output(output)

    def _resolve_output(self, output: str) -> str:
        if os.path.isabs(output):
            return output
        return os.path.join(self._output_dir, output)

    def _stem_from_output(self, path: str) -> Optional[str]:
        basename = Path(path).stem
        lowered = basename.lower()
        known = sorted(STEM_TO_MODEL.keys(), key=len, reverse=True)
        best_stem: Optional[str] = None
        best_position = -1
        for stem in known:
            marker = f"({stem})"
            position = lowered.rfind(marker)
            while position != -1:
                after = position + len(marker)
                if after == len(lowered) or lowered[after] in "_. ":
                    break
                position = lowered.rfind(marker, 0, position)
            if position > best_position:
                best_position = position
                best_stem = stem
        return best_stem

    def _check_cancelled(self, cancel_event) -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise CancelledError("Separation cancelled")

    def _report(self, progress_cb, percent: int, message: str) -> None:
        if progress_cb is not None:
            progress_cb(percent, message)
