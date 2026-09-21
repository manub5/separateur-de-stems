"""Command-line facade for the stem separator."""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from separateur_de_stems.core.catalog import fetch_catalog, top_models_for_stem
from separateur_de_stems.core.engine import SeparationEngine
from separateur_de_stems.core.errors import (
    CancelledError,
    OutputError,
    StemSeparatorError,
)
from separateur_de_stems.core.export import to_mp3_320, to_wav24
from separateur_de_stems.core.models import STEM_TO_MODEL
from separateur_de_stems.core.naming import stem_filename

CANONICAL_STEMS = tuple(STEM_TO_MODEL.keys())
DEFAULT_STEMS = "vocals,instrumental"
LIST_LIMIT = 5

_LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="separateur-de-stems",
        description="Separate an audio file into individual stems.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="Audio file to separate (WAV, FLAC, MP3, AIFF, M4A).",
    )
    parser.add_argument(
        "--stems",
        default=DEFAULT_STEMS,
        help=f"Comma-separated stems to extract (default: {DEFAULT_STEMS}).",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory for exported files (default: output).",
    )
    parser.add_argument(
        "--model-dir",
        default="models",
        help="Directory holding the separation models (default: models).",
    )
    parser.add_argument(
        "--no-mp3",
        action="store_true",
        help="Only export 24-bit WAV files, skip MP3.",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List the best available models per stem and exit.",
    )
    return parser


def parse_stems(raw: str) -> set[str]:
    return {stem.strip().lower() for stem in raw.split(",") if stem.strip()}


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_models:
        return _list_models(args.model_dir)

    if args.input is None:
        parser.print_usage(sys.stderr)
        print(
            "Erreur : le fichier d'entrée est requis (ou utilisez --list-models).",
            file=sys.stderr,
        )
        return 2

    stems = parse_stems(args.stems)
    unknown = sorted(stems - STEM_TO_MODEL.keys())
    if unknown:
        print(
            f"Erreur : piste(s) inconnue(s) : {', '.join(unknown)}",
            file=sys.stderr,
        )
        return 2

    try:
        _ensure_output_dir(args.output_dir)
        engine = SeparationEngine(args.model_dir, args.output_dir)
        outputs = engine.run(
            args.input,
            stems,
            progress_cb=_print_progress,
        )
        _export(args.input, outputs, stems, args.output_dir, args.no_mp3)
    except CancelledError:
        print("Séparation annulée.", file=sys.stderr)
        return 130
    except StemSeparatorError as error:
        print(f"Erreur : {error}", file=sys.stderr)
        return 2
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Unexpected failure")
        print("Erreur inattendue, consultez les journaux.", file=sys.stderr)
        return 2

    return 0


def _ensure_output_dir(output_dir: str) -> None:
    try:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise OutputError(
            f"Impossible de créer le dossier de sortie {output_dir} : {error}"
        ) from error


def _print_progress(percent: int, message: str) -> None:
    print(f"[{percent}%] {message}")


def _export(
    input_path: str,
    outputs: dict[str, str],
    stems: set[str],
    output_dir: str,
    no_mp3: bool,
) -> None:
    exported_wavs: list[str] = []
    intermediates: list[str] = []
    for stem in sorted(stems & outputs.keys()):
        source = outputs[stem]
        if not Path(source).is_file():
            continue
        intermediates.append(source)
        wav_path = stem_filename(input_path, stem, "wav", output_dir)
        to_wav24(source, wav_path)
        exported_wavs.append(wav_path)
        if not no_mp3:
            mp3_path = stem_filename(input_path, stem, "mp3", output_dir)
            to_mp3_320(wav_path, mp3_path)

    _remove_intermediates(intermediates, exported_wavs)


def _remove_intermediates(
    intermediates: list[str], exported_wavs: list[str]
) -> None:
    exported = {str(Path(path).resolve()) for path in exported_wavs}
    for path in intermediates:
        try:
            target = Path(path).resolve()
            if target in exported:
                continue
            target.unlink()
        except OSError:
            pass


def _list_models(model_dir: str) -> int:
    try:
        catalog = fetch_catalog(model_dir)
    except StemSeparatorError as error:
        print(f"Erreur : {error}", file=sys.stderr)
        return 2

    for stem in CANONICAL_STEMS:
        print(f"{stem} :")
        top = top_models_for_stem(catalog, stem, LIST_LIMIT)
        if not top:
            print("  (aucun modèle)")
            continue
        for filename, score in top:
            print(f"  {score:5.2f}  {filename}")
    return 0
