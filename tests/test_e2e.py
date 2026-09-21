"""End-to-end separation on a short synthetic signal.

The slow test loads a real model and may download it (network required).
"""

import os

import pytest
import soundfile as sf

from separateur_de_stems.core.engine import SeparationEngine


def test_synth_wav_is_readable(synth_wav):
    info = sf.info(synth_wav)
    assert info.frames > 0
    assert info.samplerate == 44100
    assert info.channels == 1


@pytest.mark.slow
def test_separate_vocals_synthetic(synth_wav, tmp_path):
    engine = SeparationEngine(
        model_dir="models",
        output_dir=str(tmp_path / "stems"),
    )

    result = engine.run(synth_wav, {"vocals"})

    vocal_keys = [key for key in result if "vocal" in key.lower()]
    assert vocal_keys, f"No vocal stem in result: {result}"

    for path in result.values():
        assert os.path.isfile(path)
        assert os.path.getsize(path) > 0
