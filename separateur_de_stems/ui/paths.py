"""Path resolution for development and frozen (PyInstaller) builds.

In development the models and cache live next to the project. In a frozen
bundle they go under the per-user application data directory, while models
and a bundled ffmpeg are read from PyInstaller's ``sys._MEIPASS``.

Limitation: the frozen behaviour cannot be exercised for real on Linux; it
is validated with mocks and must be re-checked on the macOS bundle.
"""

import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths

from separateur_de_stems.core.bundle_manifest import BundleManifestError, validate_model_bundle

__all__ = [
    "is_frozen",
    "default_model_dir",
    "default_cache_dir",
    "default_output_dir",
    "ffmpeg_dir",
]

_APP_DIR_NAME = "StemSeparator"


def is_frozen() -> bool:
    """Return True when running inside a PyInstaller bundle."""
    return bool(getattr(sys, "frozen", False))


def _app_data_dir() -> Path:
    """Base per-user application data directory for the bundled app."""
    location = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppDataLocation
    )
    if not location:
        location = str(Path.home())
    return Path(location) / _APP_DIR_NAME


def default_model_dir() -> str:
    """Directory holding the separation models."""
    if is_frozen():
        bundle_root = getattr(sys, "_MEIPASS", None)
        if bundle_root:
            bundled_models = Path(bundle_root) / "models"
            try:
                validate_model_bundle(bundled_models, require_distributable=True)
            except BundleManifestError:
                pass
            else:
                return str(bundled_models)
    return "models"


def default_cache_dir() -> str:
    """Directory holding downloaded caches."""
    if is_frozen():
        return str(_app_data_dir() / "cache")
    return ".cache"


def default_output_dir() -> str:
    """Default directory where separated stems are written."""
    for location_type in (
        QStandardPaths.StandardLocation.MusicLocation,
        QStandardPaths.StandardLocation.DocumentsLocation,
    ):
        location = QStandardPaths.writableLocation(location_type)
        if location:
            return location
    return str(Path.home())


def ffmpeg_dir() -> str | None:
    """Bundled ffmpeg directory, or None when it is not present."""
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        return None
    candidate = Path(meipass) / "ffmpeg"
    if candidate.is_dir():
        return str(candidate)
    return None
