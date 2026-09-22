"""Isolated, torch-free platform and accelerator detection.

This module centralises OS/accelerator heuristics so the rest of the
codebase stays testable on Linux. ``torch`` is imported lazily: importing
this module never pulls torch in.

Limitation: the real macOS behaviour (MPS / CoreML) cannot be exercised on
Linux. Those branches are validated with mocks and must be re-checked on an
Apple Silicon machine before release.
"""

import platform
import sys
from pathlib import Path

__all__ = [
    "is_apple_silicon",
    "torch_device_hint",
    "onnx_provider_hint",
    "ffmpeg_executable",
]


def ffmpeg_executable() -> str:
    """Return the ffmpeg path to use.

    In a frozen build (PyInstaller) the bundled binary lives under
    ``<sys._MEIPASS>/ffmpeg/ffmpeg``; otherwise fall back to ``ffmpeg`` so
    the system PATH is searched.
    """
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        bundled = Path(bundle_root) / "ffmpeg" / "ffmpeg"
        if bundled.is_file():
            return str(bundled)
    return "ffmpeg"


def is_apple_silicon() -> bool:
    """Return True on Darwin running on arm64 (Apple Silicon)."""
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def _torch_cuda_available() -> bool:
    """Lazily ask torch whether CUDA is available; any import error -> False."""
    try:
        import torch
    except Exception:  # noqa: BLE001 - torch may be missing or broken
        return False
    try:
        return bool(torch.cuda.is_available())
    except Exception:  # noqa: BLE001
        return False


def torch_device_hint() -> str:
    """Best device string for torch: "mps", "cuda" or "cpu".

    Apple Silicon returns "mps" without importing torch. Otherwise torch is
    imported lazily and "cuda" is returned when available.
    """
    if is_apple_silicon():
        return "mps"
    if _torch_cuda_available():
        return "cuda"
    return "cpu"


def onnx_provider_hint() -> str:
    """Best ONNX Runtime execution provider hint: "coreml", "cuda" or "cpu".

    Heuristic only: onnxruntime is intentionally NOT imported. Apple Silicon
    maps to CoreML, CUDA availability comes from torch, everything else is CPU.
    """
    if is_apple_silicon():
        return "coreml"
    if _torch_cuda_available():
        return "cuda"
    return "cpu"
