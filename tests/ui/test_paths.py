"""Tests for development and frozen path resolution.

The frozen (PyInstaller) branches cannot be exercised for real on Linux;
they are emulated by monkeypatching ``sys.frozen`` and ``sys._MEIPASS``.
Qt is run in offscreen mode.
"""

import os
import sys

import pytest

from separateur_de_stems.ui import paths


@pytest.fixture(autouse=True)
def clean_frozen(monkeypatch):
    """Ensure sys.frozen / sys._MEIPASS are absent unless a test sets them."""
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    yield


def test_is_frozen_false_in_dev():
    assert paths.is_frozen() is False


def test_is_frozen_true_when_sys_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert paths.is_frozen() is True


def test_default_model_dir_dev():
    assert paths.default_model_dir() == "models"


def test_default_cache_dir_dev():
    assert paths.default_cache_dir() == ".cache"


def test_default_model_dir_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    result = paths.default_model_dir()
    assert result.endswith("models")
    assert "StemSeparator" in result


def test_default_cache_dir_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    result = paths.default_cache_dir()
    assert result.endswith("cache")
    assert "StemSeparator" in result


def test_default_output_dir_non_empty():
    result = paths.default_output_dir()
    assert isinstance(result, str)
    assert result


def test_ffmpeg_dir_none_in_dev():
    assert paths.ffmpeg_dir() is None


def test_ffmpeg_dir_none_when_meipass_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert paths.ffmpeg_dir() is None


def test_ffmpeg_dir_returns_existing_dir(monkeypatch, tmp_path):
    meipass = tmp_path / "_meipass"
    ffmpeg = meipass / "ffmpeg"
    ffmpeg.mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    result = paths.ffmpeg_dir()
    assert result == str(ffmpeg)
    assert os.path.isdir(result)
