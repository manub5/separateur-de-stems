import os

import pytest

from separateur_de_stems.core.packaging import PackagingError, validate_build_inputs
from scripts.smoke_bundle import smoke_ffmpeg


def test_build_inputs_fail_clearly_on_incomplete_model_manifest(tmp_path):
    ffmpeg = tmp_path / "ffmpeg"
    ffprobe = tmp_path / "ffprobe"
    for binary in (ffmpeg, ffprobe):
        binary.write_text("#!/bin/sh\n")
        binary.chmod(0o755)
    i18n = tmp_path / "i18n"
    i18n.mkdir()
    (i18n / "fr.qm").write_bytes(b"qm")
    models = tmp_path / "models"
    models.mkdir()

    with pytest.raises(PackagingError, match="manifest"):
        validate_build_inputs(models, i18n, ffmpeg, ffprobe)


def test_build_inputs_reject_non_executable_tool(tmp_path):
    tool = tmp_path / "ffmpeg"
    tool.write_text("binary")
    assert not os.access(tool, os.X_OK)
    with pytest.raises(PackagingError, match="executable"):
        validate_build_inputs(tmp_path, tmp_path, tool, tool)


def test_ffmpeg_smoke_neutralizes_system_path(monkeypatch, tmp_path):
    ffmpeg = tmp_path / "ffmpeg"
    ffmpeg.write_text("#!/bin/sh\n")
    ffmpeg.chmod(0o755)
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        args[-1].write_bytes(b"mp3")

    monkeypatch.setattr("scripts.smoke_bundle.subprocess.run", fake_run)
    smoke_ffmpeg(ffmpeg, tmp_path)

    assert calls[0][1]["env"]["PATH"] == ""
    assert calls[0][0][0] == str(ffmpeg)
