"""Strict checks shared by PyInstaller and packaging smoke scripts."""

import os
from pathlib import Path

from separateur_de_stems.core.bundle_manifest import BundleManifestError, validate_model_bundle


class PackagingError(RuntimeError):
    pass


def validate_build_inputs(models_dir, translations_dir, ffmpeg, ffprobe):
    for name, executable in (("ffmpeg", ffmpeg), ("ffprobe", ffprobe)):
        path = Path(executable) if executable else Path()
        if not executable or not path.is_file() or not os.access(path, os.X_OK):
            raise PackagingError(f"Required {name} executable is absent or not executable: {executable}")
    translations = Path(translations_dir)
    if not translations.is_dir() or not any(translations.glob("*.qm")):
        raise PackagingError(f"Compiled translations are absent: {translations}")
    try:
        return validate_model_bundle(models_dir, require_distributable=True)
    except BundleManifestError as error:
        raise PackagingError(f"Offline model manifest is incomplete: {error}") from error
