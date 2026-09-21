"""Access and verification of the audio-separator model catalog."""

from numbers import Real

from separateur_de_stems.core.errors import ModelUnavailableError
from separateur_de_stems.core.models import STEM_TO_MODEL


def fetch_catalog(model_dir: str) -> dict[str, dict]:
    """Fetch the simplified model catalog without loading a separation model."""
    from audio_separator.separator import Separator

    separator = Separator(info_only=True, model_file_dir=model_dir)
    return separator.get_simplified_model_list()


def verify_selected_models(catalog: dict[str, dict], stems: set[str]) -> None:
    """Ensure that each requested stem and its selected model are available."""
    unknown_stems = sorted(stems - STEM_TO_MODEL.keys())
    if unknown_stems:
        raise ModelUnavailableError(
            f"No model available for stems: {', '.join(unknown_stems)}"
        )

    missing = sorted({STEM_TO_MODEL[stem] for stem in stems} - catalog.keys())
    if missing:
        raise ModelUnavailableError(
            "Model(s) absent from catalog: " + ", ".join(missing)
        )


def top_models_for_stem(
    catalog: dict[str, dict], stem: str, limit: int = 5
) -> list[tuple[str, float]]:
    """Return the highest numeric SDR scores for a stem."""
    if limit <= 0:
        return []

    scored_models = []
    for filename, info in catalog.items():
        score = info.get("SDR", {}).get(stem)
        if isinstance(score, Real) and not isinstance(score, bool):
            scored_models.append((filename, float(score)))

    scored_models.sort(key=lambda item: (-item[1], item[0]))
    return scored_models[:limit]
