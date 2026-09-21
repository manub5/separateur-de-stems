"""Tests for isolated platform detection.

The real macOS behaviour (MPS/CoreML) cannot be exercised on Linux; these
tests emulate Darwin/arm64 with mocks and a fake torch injected in
``sys.modules``. Torch is never imported for real.
"""

import builtins
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


def test_module_import_does_not_import_torch(monkeypatch):
    block_torch_import(monkeypatch)
    sys.modules.pop("torch", None)
    sys.modules.pop("separateur_de_stems.core.platform", None)
    import importlib

    reloaded = importlib.import_module("separateur_de_stems.core.platform")
    assert reloaded is not None
    assert "torch" not in sys.modules
