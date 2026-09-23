# -*- mode: python ; coding: utf-8 -*-
import shutil
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules
from separateur_de_stems.core.packaging import validate_build_inputs

ROOT = Path(SPECPATH).parent
APP_NAME = "StemSeparator"

ffmpeg_src = shutil.which("ffmpeg")
ffprobe_src = shutil.which("ffprobe")
i18n_dir = ROOT / "separateur_de_stems" / "ui" / "i18n"
model_assets = validate_build_inputs(
    ROOT / "models", i18n_dir, ffmpeg_src, ffprobe_src,
    ROOT / "packaging" / "redistributed-binaries.json",
)

datas = []
datas += collect_data_files("audio_separator")
datas += collect_data_files("separateur_de_stems")
datas += [(str(asset), "models") for asset in model_assets]
datas.append((str(ROOT / "packaging" / "redistributed-binaries.json"), "ffmpeg"))

# Compiled Qt translations, resolved at runtime from
# <sys._MEIPASS>/separateur_de_stems/ui/i18n.
for qm in sorted(i18n_dir.glob("*.qm")):
    datas.append((str(qm), "separateur_de_stems/ui/i18n"))

hiddenimports = []
hiddenimports += collect_submodules("torch")
for module in ("audio_separator.separator", "onnxruntime", "soundfile", "librosa"):
    try:
        hiddenimports += collect_submodules(module)
    except Exception:
        pass

binaries = []
binaries += collect_dynamic_libs("onnxruntime")

binaries.append((ffmpeg_src, "ffmpeg"))
binaries.append((ffprobe_src, "ffmpeg"))

excludes = [
    "tkinter", "matplotlib", "pytest", "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore", "PySide6.QtCharts",
]

a = Analysis(
    [str(ROOT / "separateur_de_stems" / "ui" / "app.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[str(ROOT / "packaging" / "runtime_hook.py")],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name=APP_NAME)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        bundle_identifier="io.github.numa91.stemseparator",
        info_plist={"NSHighResolutionCapable": True},
    )
