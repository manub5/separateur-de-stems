"""Command-line facade for the stem separator."""

import argparse
import logging
import sys
from typing import Optional

from separateur_de_stems.core.catalog import fetch_catalog, top_models_for_stem
from separateur_de_stems.core.errors import (
    CancelledError,
    StemSeparatorError,
)
from separateur_de_stems.core.models import STEM_TO_MODEL
from separateur_de_stems.core.pipeline import run_pipeline
from separateur_de_stems.core.platform import ensure_bundled_ffmpeg_on_path

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
    ensure_bundled_ffmpeg_on_path()

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
    if not stems:
        print(
            "Erreur : aucune piste sélectionnée (--stems est vide).",
            file=sys.stderr,
        )
        return 2
    unknown = sorted(stems - STEM_TO_MODEL.keys())
    if unknown:
        print(
            f"Erreur : piste(s) inconnue(s) : {', '.join(unknown)}",
            file=sys.stderr,
        )
        return 2

    try:
        run_pipeline(
            args.input,
            stems,
            args.output_dir,
            args.model_dir,
            include_mp3=not args.no_mp3,
            progress_cb=_print_progress,
        )
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


def _print_progress(percent: int, message: str) -> None:
    print(f"[{percent}%] {message}")


def _list_models(model_dir: str) -> int:
    try:
        catalog = fetch_catalog(model_dir)
    except StemSeparatorError as error:
        print(f"Erreur : {error}", file=sys.stderr)
        return 2
    except Exception as error:  # noqa: BLE001
        _LOGGER.error("Unexpected failure while listing models: %s", error)
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
