"""Every offered stem must route to its selected model and yield real audio."""

from pathlib import Path

import pytest
import soundfile as sf

from separateur_de_stems.core.engine import SeparationEngine
from separateur_de_stems.core.models import STEM_TO_MODEL


@pytest.mark.parametrize("stem", tuple(STEM_TO_MODEL))
def test_each_stem_selects_model_and_writes_synthetic_audio(
    stem, synth_wav, tmp_path
):
    loaded = []
    output_dir = tmp_path / "out"

    class SyntheticSeparator:
        def __init__(self, **kwargs):
            assert kwargs["model_file_dir"] == str(tmp_path / "models")

        def load_model(self, filename):
            loaded.append(filename)

        def separate(self, input_path):
            data, rate = sf.read(input_path)
            path = output_dir / f"synth_({stem.title()}).wav"
            sf.write(path, data, rate)
            return [str(path)]

    engine = SeparationEngine(
        model_dir=str(tmp_path / "models"),
        output_dir=str(output_dir),
        separator_factory=SyntheticSeparator,
        catalog_fetcher=lambda directory: {filename: {} for filename in set(STEM_TO_MODEL.values())},
    )

    outputs = engine.run(synth_wav, {stem})
    assert loaded == [STEM_TO_MODEL[stem]]
    assert stem in outputs
    assert Path(outputs[stem]).is_file()
    assert sf.info(outputs[stem]).frames > 0
