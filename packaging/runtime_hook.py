"""PyInstaller runtime hook: make frozen multiprocessing spawn safe.

Also exposes the bundled ffmpeg to ``audio-separator`` (which shells out to
``ffmpeg -version``) and to ``pydub`` (which resolves ffmpeg through ``PATH``),
so no system ffmpeg is required. ``sys._MEIPASS`` is set by PyInstaller before
this hook runs, and remains set in every spawned child.
"""
import multiprocessing

multiprocessing.freeze_support()

from separateur_de_stems.core.platform import ensure_bundled_ffmpeg_on_path

ensure_bundled_ffmpeg_on_path()
