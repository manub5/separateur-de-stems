from pathlib import Path

SPEC = Path("packaging/stem-separator.spec")
RUNTIME_HOOK = Path("packaging/runtime_hook.py")


def test_spec_exists():
    assert SPEC.is_file()


def test_runtime_hook_calls_freeze_support():
    text = RUNTIME_HOOK.read_text()
    assert "freeze_support" in text


def test_runtime_hook_exposes_bundled_ffmpeg_on_path():
    text = RUNTIME_HOOK.read_text()
    assert "ensure_bundled_ffmpeg_on_path" in text


def test_spec_collects_i18n_and_audio_separator():
    text = SPEC.read_text()
    assert "audio_separator" in text
    assert "i18n" in text
    assert "ffmpeg" in text


def test_spec_uses_real_bundle_identifier():
    text = SPEC.read_text()
    assert "bundle_identifier" in text
    assert "com.example" not in text
    assert "io.github.numa91.stemseparator" in text
