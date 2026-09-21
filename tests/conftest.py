"""Shared pytest fixtures and markers."""

import numpy as np
import pytest
import soundfile as sf


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "slow: end-to-end test that loads a real model (may download it)",
    )


@pytest.fixture
def synth_wav(tmp_path):
    """Mono 2 s, 44100 Hz, PCM_16, 440 Hz sine wave."""
    sample_rate = 44100
    duration = 2.0
    frequency = 440.0
    timeline = np.linspace(
        0.0, duration, int(sample_rate * duration), endpoint=False
    )
    tone = 0.5 * np.sin(2.0 * np.pi * frequency * timeline)
    path = tmp_path / "synth.wav"
    sf.write(str(path), tone, sample_rate, subtype="PCM_16")
    return str(path)
