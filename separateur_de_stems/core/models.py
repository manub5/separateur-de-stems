from dataclasses import dataclass

from separateur_de_stems.core.errors import ModelUnavailableError


SUPPORTED_EXTENSIONS = {".wav", ".flac", ".mp3", ".aiff", ".aif", ".m4a"}

STEM_TO_MODEL = {
    "vocals": "vocals_mel_band_roformer.ckpt",
    "instrumental": "model_bs_roformer_ep_317_sdr_12.9755.ckpt",
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
    "model_bs_roformer_ep_317_sdr_12.9755.ckpt": ModelSpec(
        "model_bs_roformer_ep_317_sdr_12.9755.ckpt",
        ("vocals", "instrumental"),
        {"vocals": None, "instrumental": 16.5},
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
    return [_MODEL_SPECS[filename] for filename in filenames]
