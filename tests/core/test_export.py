import subprocess
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from separateur_de_stems.core.errors import OutputError
from separateur_de_stems.core.export import to_mp3_320, to_wav24

SAMPLE_RATE = 8000


def write_source(tmp_path, name="stem.wav", channels=2, subtype="PCM_16"):
    frames = int(SAMPLE_RATE * 0.1)
    time = np.arange(frames) / SAMPLE_RATE
    data = np.stack(
        [np.sin(2 * np.pi * 440 * time) for _ in range(channels)], axis=1
    ).astype(np.float32)
    source = tmp_path / name
    sf.write(str(source), data, SAMPLE_RATE, subtype=subtype)
    return source, data


def test_to_wav24_returns_dest(tmp_path):
    source, _ = write_source(tmp_path)
    dest = tmp_path / "out" / "stem24.wav"

    result = to_wav24(str(source), str(dest))

    assert result == str(dest)


def test_to_wav24_writes_pcm24_subtype(tmp_path):
    source, _ = write_source(tmp_path, subtype="PCM_16")
    dest = tmp_path / "out" / "stem24.wav"

    to_wav24(str(source), str(dest))

    assert sf.info(str(dest)).subtype == "PCM_24"


def test_to_wav24_preserves_channel_count(tmp_path):
    source, _ = write_source(tmp_path, channels=2)
    dest = tmp_path / "out" / "stem24.wav"

    to_wav24(str(source), str(dest))

    assert sf.info(str(dest)).channels == 2


def test_to_wav24_creates_parent_directory(tmp_path):
    source, _ = write_source(tmp_path)
    dest = tmp_path / "nested" / "deeper" / "stem24.wav"

    to_wav24(str(source), str(dest))

    assert dest.is_file()


def test_to_wav24_missing_source_raises_output_error(tmp_path):
    dest = tmp_path / "stem24.wav"

    with pytest.raises(OutputError):
        to_wav24(str(tmp_path / "missing.wav"), str(dest))


def test_to_wav24_read_failure_raises_output_error(tmp_path):
    source = tmp_path / "corrupt.wav"
    source.write_bytes(b"not audio")
    dest = tmp_path / "stem24.wav"

    with pytest.raises(OutputError):
        to_wav24(str(source), str(dest))


def test_to_wav24_leaves_no_partial_dest_on_write_failure(tmp_path, monkeypatch):
    source, _ = write_source(tmp_path)
    dest = tmp_path / "stem24.wav"

    def exploding_write(*args, **kwargs):
        Path(args[0]).write_bytes(b"partial")
        raise RuntimeError("write boom")

    monkeypatch.setattr(sf, "write", exploding_write)

    with pytest.raises(OutputError):
        to_wav24(str(source), str(dest))

    assert not dest.exists()


def test_to_wav24_does_not_delete_preexisting_dest_on_failure(tmp_path, monkeypatch):
    source, _ = write_source(tmp_path)
    dest = tmp_path / "stem24.wav"
    dest.write_bytes(b"keep me")

    def exploding_read(*args, **kwargs):
        raise RuntimeError("read boom")

    monkeypatch.setattr(sf, "read", exploding_read)

    with pytest.raises(OutputError):
        to_wav24(str(source), str(dest))

    assert dest.read_bytes() == b"keep me"


def test_to_mp3_320_returns_dest(tmp_path):
    source, _ = write_source(tmp_path)
    dest = tmp_path / "out" / "stem.mp3"

    result = to_mp3_320(str(source), str(dest))

    assert result == str(dest)


def test_to_mp3_320_creates_non_empty_file(tmp_path):
    source, _ = write_source(tmp_path)
    dest = tmp_path / "out" / "stem.mp3"

    to_mp3_320(str(source), str(dest))

    assert dest.is_file()
    assert dest.stat().st_size > 0


def test_to_mp3_320_creates_parent_directory(tmp_path):
    source, _ = write_source(tmp_path)
    dest = tmp_path / "nested" / "deeper" / "stem.mp3"

    to_mp3_320(str(source), str(dest))

    assert dest.is_file()


def test_to_mp3_320_uses_argument_list_without_shell(tmp_path, monkeypatch):
    source, _ = write_source(tmp_path)
    dest = tmp_path / "out" / "stem.mp3"
    captured = {}

    class Result:
        stderr = b""

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(b"mp3")
        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)

    to_mp3_320(str(source), str(dest))

    args = captured["args"]
    assert isinstance(args, list)
    assert "-b:a" in args
    assert args[args.index("-b:a") + 1] == "320k"
    assert "-y" in args
    assert args[0] == "ffmpeg"
    assert "shell" not in captured["kwargs"]
    assert captured["kwargs"]["capture_output"] is True
    assert captured["kwargs"]["check"] is True


def test_to_mp3_uses_resolved_ffmpeg(tmp_path, monkeypatch):
    source, _ = write_source(tmp_path)
    dest = tmp_path / "out" / "stem.mp3"
    captured = {}

    class Result:
        stderr = b""

    def fake_run(args, **kwargs):
        captured["args"] = args
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(b"mp3")
        return Result()

    monkeypatch.setattr("separateur_de_stems.core.export.ffmpeg_executable", lambda: "/bundle/ffmpeg")
    monkeypatch.setattr(subprocess, "run", fake_run)

    to_mp3_320(str(source), str(dest))

    assert captured["args"][0] == "/bundle/ffmpeg"


def test_to_mp3_320_missing_source_raises_output_error(tmp_path):
    dest = tmp_path / "stem.mp3"

    with pytest.raises(OutputError):
        to_mp3_320(str(tmp_path / "missing.wav"), str(dest))


def test_to_mp3_320_missing_ffmpeg_raises_output_error(tmp_path, monkeypatch):
    source, _ = write_source(tmp_path)
    dest = tmp_path / "stem.mp3"

    def missing_run(*args, **kwargs):
        raise FileNotFoundError("ffmpeg not found")

    monkeypatch.setattr(subprocess, "run", missing_run)

    with pytest.raises(OutputError):
        to_mp3_320(str(source), str(dest))

    assert not dest.exists()


def test_to_mp3_320_ffmpeg_failure_raises_output_error_with_stderr(tmp_path, monkeypatch):
    source, _ = write_source(tmp_path)
    dest = tmp_path / "stem.mp3"

    def failing_run(args, **kwargs):
        Path(dest).write_bytes(b"partial")
        raise subprocess.CalledProcessError(
            returncode=1, cmd=args, stderr=b"boom-encoding-failed"
        )

    monkeypatch.setattr(subprocess, "run", failing_run)

    with pytest.raises(OutputError) as exc_info:
        to_mp3_320(str(source), str(dest))

    assert "boom-encoding-failed" in str(exc_info.value)
    assert not dest.exists()


def test_to_mp3_320_preserves_cause(tmp_path, monkeypatch):
    source, _ = write_source(tmp_path)
    dest = tmp_path / "stem.mp3"
    original = subprocess.CalledProcessError(returncode=1, cmd=["ffmpeg"], stderr=b"x")

    def failing_run(*args, **kwargs):
        raise original

    monkeypatch.setattr(subprocess, "run", failing_run)

    with pytest.raises(OutputError) as exc_info:
        to_mp3_320(str(source), str(dest))

    assert exc_info.value.__cause__ is original
