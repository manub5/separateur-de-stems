import os
import json
import re
from dataclasses import dataclass, replace
from pathlib import Path

from separateur_de_stems.core.errors import ModelUnavailableError


SUPPORTED_EXTENSIONS = {".wav", ".flac", ".mp3", ".aiff", ".aif", ".m4a"}


def is_supported_audio(path: str) -> bool:
    """Return True when ``path``'s real extension is a supported audio one.

    Uses ``os.path.splitext`` so a name like ``song.wav.exe`` or a hidden
    file named exactly ``.wav`` is rejected, unlike a naive ``endswith``
    check. Shared by the CLI and the UI to keep one source of truth.
    """
    extension = os.path.splitext(path)[1].lower()
    return extension in SUPPORTED_EXTENSIONS

STEM_TO_MODEL = {
    "vocals": "vocals_mel_band_roformer.ckpt",
    "instrumental": "bs_roformer_vocals_gabox.ckpt",
    "drums": "htdemucs_ft.yaml",
    "bass": "hdemucs_mmi.yaml",
    "guitar": "htdemucs_6s.yaml",
    "piano": "htdemucs_6s.yaml",
}

_CANONICAL_STEMS = ("vocals", "instrumental", "drums", "bass", "guitar", "piano")


@dataclass(frozen=True)
class ModelSpec:
    filename: str
    stems: tuple[str, ...]
    sdr: dict[str, float | None]

    def __post_init__(self) -> None:
        object.__setattr__(self, "sdr", dict(self.sdr))


_MODEL_SPECS = {
    "vocals_mel_band_roformer.ckpt": ModelSpec(
        "vocals_mel_band_roformer.ckpt",
        ("vocals", "instrumental"),
        {"vocals": 12.6, "instrumental": None},
    ),
    "bs_roformer_vocals_gabox.ckpt": ModelSpec(
        "bs_roformer_vocals_gabox.ckpt",
        ("vocals", "instrumental"),
        {"vocals": None, "instrumental": 17.2147},
    ),
    "htdemucs_ft.yaml": ModelSpec(
        "htdemucs_ft.yaml",
        ("vocals", "drums", "bass", "other"),
        {"vocals": None, "drums": 10.0, "bass": None, "other": None},
    ),
    "hdemucs_mmi.yaml": ModelSpec(
        "hdemucs_mmi.yaml",
        ("vocals", "drums", "bass", "other"),
        {"vocals": None, "drums": None, "bass": 12.2, "other": None},
    ),
    "htdemucs_6s.yaml": ModelSpec(
        "htdemucs_6s.yaml",
        ("vocals", "drums", "bass", "guitar", "piano", "other"),
        {
            "vocals": None,
            "drums": None,
            "bass": None,
            "guitar": None,
            "piano": None,
            "other": None,
        },
    ),
}


def select_models(stems: set[str]) -> list[ModelSpec]:
    unknown_stems = sorted(stems - STEM_TO_MODEL.keys())
    if unknown_stems:
        raise ModelUnavailableError(
            f"No model available for stems: {', '.join(unknown_stems)}"
        )

    filenames = dict.fromkeys(
        STEM_TO_MODEL[stem] for stem in _CANONICAL_STEMS if stem in stems
    )
    return [replace(_MODEL_SPECS[filename]) for filename in filenames]


def missing_assets_by_stem(model_dir: str | Path) -> dict[str, tuple[str, ...]]:
    """List absent model assets for each stem without hashing multi-GB weights in Qt."""
    root = Path(model_dir)
    try:
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        selected = {entry["filename"]: entry["asset_paths"] for entry in manifest["models"]}
        assets = {entry["path"]: entry for entry in manifest["assets"]}
        if not all(
            isinstance(filename, str)
            and isinstance(paths, list)
            and paths
            and all(isinstance(name, str) and Path(name).name == name for name in paths)
            for filename, paths in selected.items()
        ) or not all(isinstance(name, str) for name in assets):
            raise ValueError("Invalid model asset entries")
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, AttributeError):
        return {stem: ("manifest.json",) for stem in STEM_TO_MODEL}
    result = {}
    for stem, filename in STEM_TO_MODEL.items():
        missing = []
        for name in selected.get(filename, [filename]):
            metadata = assets.get(name)
            path = root / name
            try:
                valid = (
                    isinstance(metadata, dict)
                    and isinstance(metadata.get("size"), int)
                    and metadata["size"] > 0
                    and isinstance(metadata.get("sha256"), str)
                    and re.fullmatch(r"[0-9a-f]{64}", metadata["sha256"]) is not None
                    and path.is_file()
                    and not path.is_symlink()
                    and path.stat().st_size == metadata["size"]
                )
            except OSError:
                valid = False
            if not valid:
                missing.append(name)
        if missing:
            result[stem] = tuple(missing)
    return result
