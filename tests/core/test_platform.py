"""Tests for isolated platform detection.

The real macOS behaviour (MPS/CoreML) cannot be exercised on Linux; these
tests emulate Darwin/arm64 with mocks and a fake torch injected in
``sys.modules``. Torch is never imported for real.
"""

import builtins
import os
import sys
import types

import pytest

from separateur_de_stems.core import platform as platform_mod


@pytest.fixture(autouse=True)
def clean_torch():
    """Ensure no real torch is present before/after each test."""
    saved = sys.modules.pop("torch", None)
    yield
    sys.modules.pop("torch", None)
    if saved is not None:
        sys.modules["torch"] = saved


def patch_system(monkeypatch, system: str, machine: str) -> None:
    monkeypatch.setattr(platform_mod.platform, "system", lambda: system)
    monkeypatch.setattr(platform_mod.platform, "machine", lambda: machine)


def install_fake_torch(monkeypatch, available: bool) -> None:
    fake = types.ModuleType("torch")
    fake.cuda = types.SimpleNamespace(is_available=lambda: available)
    monkeypatch.setitem(sys.modules, "torch", fake)


def block_torch_import(monkeypatch) -> None:
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "torch" or name.startswith("torch."):
            raise ImportError("torch is not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)


def test_torch_device_hint_cpu_when_import_raises(monkeypatch):
    patch_system(monkeypatch, "Linux", "x86_64")
    real_import = builtins.__import__

    def broken_import(name, *args, **kwargs):
        if name == "torch" or name.startswith("torch."):
            raise OSError("torch shared library is broken")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", broken_import)
    assert platform_mod.torch_device_hint() == "cpu"


def test_is_apple_silicon_true(monkeypatch):
    patch_system(monkeypatch, "Darwin", "arm64")
    assert platform_mod.is_apple_silicon() is True


@pytest.mark.parametrize(
    ("system", "machine"),
    [
        ("Darwin", "x86_64"),
        ("Linux", "arm64"),
        ("Linux", "x86_64"),
        ("Windows", "AMD64"),
    ],
)
def test_is_apple_silicon_false(monkeypatch, system, machine):
    patch_system(monkeypatch, system, machine)
    assert platform_mod.is_apple_silicon() is False


def test_torch_device_hint_mps_without_import(monkeypatch):
    patch_system(monkeypatch, "Darwin", "arm64")
    block_torch_import(monkeypatch)
    sys.modules.pop("torch", None)
    assert platform_mod.torch_device_hint() == "mps"
    assert "torch" not in sys.modules


def test_torch_device_hint_cuda(monkeypatch):
    patch_system(monkeypatch, "Linux", "x86_64")
    install_fake_torch(monkeypatch, available=True)
    assert platform_mod.torch_device_hint() == "cuda"


def test_torch_device_hint_cpu_when_no_cuda(monkeypatch):
    patch_system(monkeypatch, "Linux", "x86_64")
    install_fake_torch(monkeypatch, available=False)
    assert platform_mod.torch_device_hint() == "cpu"


def test_torch_device_hint_cpu_when_torch_missing(monkeypatch):
    patch_system(monkeypatch, "Linux", "x86_64")
    block_torch_import(monkeypatch)
    assert platform_mod.torch_device_hint() == "cpu"


def test_torch_device_hint_cpu_on_import_exception(monkeypatch):
    patch_system(monkeypatch, "Linux", "x86_64")

    class ExplodingModule(types.ModuleType):
        @property
        def cuda(self):
            raise RuntimeError("boom")

    monkeypatch.setitem(sys.modules, "torch", ExplodingModule("torch"))
    assert platform_mod.torch_device_hint() == "cpu"


def test_onnx_provider_hint_coreml(monkeypatch):
    patch_system(monkeypatch, "Darwin", "arm64")
    block_torch_import(monkeypatch)
    assert platform_mod.onnx_provider_hint() == "coreml"


def test_onnx_provider_hint_cuda(monkeypatch):
    patch_system(monkeypatch, "Linux", "x86_64")
    install_fake_torch(monkeypatch, available=True)
    assert platform_mod.onnx_provider_hint() == "cuda"


def test_onnx_provider_hint_cpu(monkeypatch):
    patch_system(monkeypatch, "Linux", "x86_64")
    install_fake_torch(monkeypatch, available=False)
    assert platform_mod.onnx_provider_hint() == "cpu"


def test_onnx_provider_hint_cpu_when_torch_missing(monkeypatch):
    patch_system(monkeypatch, "Linux", "x86_64")
    block_torch_import(monkeypatch)
    assert platform_mod.onnx_provider_hint() == "cpu"


def test_ffmpeg_executable_prefers_bundled(monkeypatch, tmp_path):
    bundle = tmp_path / "bundle"
    bundled = bundle / "ffmpeg" / "ffmpeg"
    bundled.parent.mkdir(parents=True)
    bundled.write_bytes(b"")
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)

    assert platform_mod.ffmpeg_executable() == str(bundled)


def test_ffmpeg_executable_falls_back_to_path(monkeypatch):
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)

    assert platform_mod.ffmpeg_executable() == "ffmpeg"


def test_ffmpeg_executable_ignores_directory_named_ffmpeg(monkeypatch, tmp_path):
    bundle = tmp_path / "bundle"
    fake_binary = bundle / "ffmpeg" / "ffmpeg"
    fake_binary.mkdir(parents=True)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)

    assert platform_mod.ffmpeg_executable() == "ffmpeg"


@pytest.fixture
def restore_path():
    """Restore ``os.environ["PATH"]`` and pydub converter after each test."""
    original = os.environ.get("PATH")
    from pydub import AudioSegment

    original_converter = AudioSegment.converter
    yield
    if original is None:
        os.environ.pop("PATH", None)
    else:
        os.environ["PATH"] = original
    AudioSegment.converter = original_converter


def _make_bundled_ffmpeg(tmp_path):
    bundle = tmp_path / "bundle"
    ffmpeg_dir = bundle / "ffmpeg"
    ffmpeg_dir.mkdir(parents=True)
    binary = ffmpeg_dir / "ffmpeg"
    binary.write_bytes(b"#!/bin/sh\n")
    binary.chmod(0o755)
    return bundle, ffmpeg_dir, binary


def test_ensure_bundled_ffmpeg_prepends_directory_to_path(
    monkeypatch, tmp_path, restore_path
):
    bundle, ffmpeg_dir, binary = _make_bundled_ffmpeg(tmp_path)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    result = platform_mod.ensure_bundled_ffmpeg_on_path()

    assert result == str(binary)
    assert os.environ["PATH"].split(os.pathsep)[0] == str(ffmpeg_dir)


def test_ensure_bundled_ffmpeg_sets_pydub_converter(
    monkeypatch, tmp_path, restore_path
):
    from pydub import AudioSegment

    bundle, _, binary = _make_bundled_ffmpeg(tmp_path)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)

    platform_mod.ensure_bundled_ffmpeg_on_path()

    assert AudioSegment.converter == str(binary)


def test_ensure_bundled_ffmpeg_is_idempotent(monkeypatch, tmp_path, restore_path):
    bundle, ffmpeg_dir, _ = _make_bundled_ffmpeg(tmp_path)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)

    platform_mod.ensure_bundled_ffmpeg_on_path()
    first_path = os.environ["PATH"]
    platform_mod.ensure_bundled_ffmpeg_on_path()

    assert os.environ["PATH"] == first_path
    entries = os.environ["PATH"].split(os.pathsep)
    assert entries.count(str(ffmpeg_dir)) == 1


def test_ensure_bundled_ffmpeg_noop_without_meipass(monkeypatch, restore_path):
    from pydub import AudioSegment

    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    original_converter = AudioSegment.converter

    result = platform_mod.ensure_bundled_ffmpeg_on_path()

    assert result is None
    assert os.environ["PATH"] == "/usr/bin:/bin"
    assert AudioSegment.converter == original_converter


def test_ensure_bundled_ffmpeg_noop_when_binary_missing(
    monkeypatch, tmp_path, restore_path
):
    bundle = tmp_path / "bundle"
    (bundle / "ffmpeg").mkdir(parents=True)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    result = platform_mod.ensure_bundled_ffmpeg_on_path()

    assert result is None
    assert os.environ["PATH"] == "/usr/bin:/bin"


def test_ensure_bundled_ffmpeg_ignores_non_executable_binary(
    monkeypatch, tmp_path, restore_path
):
    bundle, _, binary = _make_bundled_ffmpeg(tmp_path)
    binary.chmod(0o644)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    result = platform_mod.ensure_bundled_ffmpeg_on_path()

    assert result is None
    assert os.environ["PATH"] == "/usr/bin:/bin"


def test_ensure_bundled_ffmpeg_keeps_existing_path_entries(
    monkeypatch, tmp_path, restore_path
):
    bundle, ffmpeg_dir, _ = _make_bundled_ffmpeg(tmp_path)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    platform_mod.ensure_bundled_ffmpeg_on_path()

    entries = os.environ["PATH"].split(os.pathsep)
    assert entries[0] == str(ffmpeg_dir)
    assert "/usr/bin" in entries
    assert "/bin" in entries


def test_ensure_bundled_ffmpeg_seen_by_pydub_which(monkeypatch, tmp_path, restore_path):
    """The spawned children inherit ``os.environ``; ``pydub.utils.which`` too."""
    from pydub.utils import which

    bundle, _, binary = _make_bundled_ffmpeg(tmp_path)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    platform_mod.ensure_bundled_ffmpeg_on_path()

    assert which("ffmpeg") == str(binary)


def test_module_import_does_not_import_torch(monkeypatch):
    block_torch_import(monkeypatch)
    sys.modules.pop("torch", None)
    sys.modules.pop("separateur_de_stems.core.platform", None)
    import importlib

    reloaded = importlib.import_module("separateur_de_stems.core.platform")
    assert reloaded is not None
    assert "torch" not in sys.modules
