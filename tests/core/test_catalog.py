import sys
import types

import pytest

from separateur_de_stems.core.catalog import (
    fetch_catalog,
    top_models_for_stem,
    verify_selected_models,
)
from separateur_de_stems.core.errors import ModelUnavailableError
from separateur_de_stems.core.models import STEM_TO_MODEL


def test_fetch_catalog_uses_info_only_and_requested_model_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_catalog = {"model.ckpt": {"SDR": {"vocals": 1.0}}}
    received_options: list[dict[str, object]] = []

    class FakeSeparator:
        def __init__(self, **options: object) -> None:
            received_options.append(options)

        def get_simplified_model_list(self) -> dict[str, dict]:
            return expected_catalog

    separator_module = types.ModuleType("audio_separator.separator")
    separator_module.Separator = FakeSeparator  # type: ignore[attr-defined]
    package = types.ModuleType("audio_separator")
    package.__path__ = []  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "audio_separator", package)
    monkeypatch.setitem(sys.modules, "audio_separator.separator", separator_module)

    assert fetch_catalog("models") is expected_catalog
    assert received_options == [{"info_only": True, "model_file_dir": "models"}]


def test_verify_selected_models_accepts_available_models() -> None:
    catalog = {filename: {} for filename in set(STEM_TO_MODEL.values())}

    verify_selected_models(catalog, set(STEM_TO_MODEL))


def test_verify_selected_models_lists_missing_filenames_once_and_sorted() -> None:
    catalog = {STEM_TO_MODEL["vocals"]: {}}

    with pytest.raises(ModelUnavailableError) as exc_info:
        verify_selected_models(catalog, {"piano", "drums", "guitar"})

    assert str(exc_info.value) == (
        "Model(s) absent from catalog: htdemucs_6s.yaml, htdemucs_ft.yaml"
    )


def test_verify_selected_models_rejects_unknown_stem_without_key_error() -> None:
    with pytest.raises(ModelUnavailableError, match="saxophone"):
        verify_selected_models({}, {"saxophone"})


def test_top_models_for_stem_sorts_numeric_scores_and_applies_limit() -> None:
    catalog = {
        "third.ckpt": {"SDR": {"vocals": 3}},
        "first.ckpt": {"SDR": {"vocals": 7.5}},
        "second.ckpt": {"SDR": {"vocals": 5.0}},
    }

    assert top_models_for_stem(catalog, "vocals", limit=2) == [
        ("first.ckpt", 7.5),
        ("second.ckpt", 5.0),
    ]


def test_top_models_for_stem_ignores_none_missing_and_non_numeric_scores() -> None:
    catalog = {
        "none.ckpt": {"SDR": {"vocals": None}},
        "missing.ckpt": {"SDR": {"drums": 2.0}},
        "no-sdr.ckpt": {},
        "text.ckpt": {"SDR": {"vocals": "9.0"}},
        "valid.ckpt": {"SDR": {"vocals": 4}},
    }

    assert top_models_for_stem(catalog, "vocals") == [("valid.ckpt", 4)]


def test_top_models_for_stem_breaks_score_ties_by_filename() -> None:
    catalog = {
        "zulu.ckpt": {"SDR": {"vocals": 8.0}},
        "alpha.ckpt": {"SDR": {"vocals": 8.0}},
    }

    assert top_models_for_stem(catalog, "vocals") == [
        ("alpha.ckpt", 8.0),
        ("zulu.ckpt", 8.0),
    ]


@pytest.mark.parametrize("limit", [0, -1])
def test_top_models_for_stem_returns_empty_for_non_positive_limit(limit: int) -> None:
    malformed_catalog = {"model.ckpt": None}

    assert top_models_for_stem(malformed_catalog, "vocals", limit) == []
