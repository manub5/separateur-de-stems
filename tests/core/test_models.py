import pytest

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
    ModelSpec,
    select_models,
)


EXPECTED_STEM_TO_MODEL = {
    "vocals": "vocals_mel_band_roformer.ckpt",
    "instrumental": "model_bs_roformer_ep_317_sdr_12.9755.ckpt",
    "drums": "htdemucs_ft.yaml",
    "bass": "hdemucs_mmi.yaml",
    "guitar": "htdemucs_6s.yaml",
    "piano": "htdemucs_6s.yaml",
}


def test_project_errors_inherit_directly_from_base_error() -> None:
    error_types = (
        UnsupportedFormatError,
        ModelUnavailableError,
        OutputError,
        CancelledError,
    )

    assert all(error_type.__bases__ == (StemSeparatorError,) for error_type in error_types)


def test_supported_extensions_contains_all_input_formats() -> None:
    assert SUPPORTED_EXTENSIONS == {".wav", ".flac", ".mp3", ".aiff", ".aif", ".m4a"}


@pytest.mark.parametrize(("stem", "filename"), EXPECTED_STEM_TO_MODEL.items())
def test_each_stem_maps_to_expected_model(stem: str, filename: str) -> None:
    assert STEM_TO_MODEL[stem] == filename


def test_select_models_returns_vocals_model_metadata() -> None:
    assert select_models({"vocals"}) == [
        ModelSpec(
            filename="vocals_mel_band_roformer.ckpt",
            stems=("vocals", "instrumental"),
            sdr={"vocals": 12.6, "instrumental": None},
        )
    ]


def test_select_models_deduplicates_shared_guitar_and_piano_model() -> None:
    assert select_models({"guitar", "piano"}) == [
        ModelSpec(
            filename="htdemucs_6s.yaml",
            stems=("vocals", "drums", "bass", "guitar", "piano", "other"),
            sdr={
                "vocals": None,
                "drums": None,
                "bass": None,
                "guitar": None,
                "piano": None,
                "other": None,
            },
        )
    ]


def test_select_models_uses_canonical_order() -> None:
    result = select_models({"piano", "bass", "vocals", "drums", "instrumental"})

    assert [model.filename for model in result] == [
        "vocals_mel_band_roformer.ckpt",
        "model_bs_roformer_ep_317_sdr_12.9755.ckpt",
        "htdemucs_ft.yaml",
        "hdemucs_mmi.yaml",
        "htdemucs_6s.yaml",
    ]


def test_select_models_returns_empty_list_for_empty_set() -> None:
    assert select_models(set()) == []


@pytest.mark.parametrize(
    ("stems", "unknown_stems"),
    [
        ({"saxophone"}, ["saxophone"]),
        ({"zither", "vocals", "accordion"}, ["accordion", "zither"]),
    ],
)
def test_select_models_lists_unknown_stems_sorted(
    stems: set[str], unknown_stems: list[str]
) -> None:
    with pytest.raises(ModelUnavailableError) as exc_info:
        select_models(stems)

    message = str(exc_info.value)
    positions = [message.index(stem) for stem in unknown_stems]
    assert positions == sorted(positions)


def test_model_spec_exposes_frozen_fields() -> None:
    spec = ModelSpec("model.ckpt", ("vocals",), {"vocals": 1.0})

    with pytest.raises(AttributeError):
        spec.filename = "other.ckpt"  # type: ignore[misc]


def test_model_spec_copies_sdr_for_each_instance() -> None:
    source_sdr = {"vocals": 1.0}
    first = ModelSpec("model.ckpt", ("vocals",), source_sdr)
    second = ModelSpec("model.ckpt", ("vocals",), source_sdr)

    source_sdr["vocals"] = 2.0
    first.sdr["vocals"] = 3.0

    assert second.sdr == {"vocals": 1.0}
