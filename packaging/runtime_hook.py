"""PyInstaller runtime hook: make frozen multiprocessing spawn safe."""
import multiprocessing

multiprocessing.freeze_support()
