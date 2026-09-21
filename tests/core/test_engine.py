import logging
import os
import threading
from pathlib import Path

import pytest

from separateur_de_stems.core.engine import SeparationEngine
from separateur_de_stems.core.errors import (
    CancelledError,
    ModelUnavailableError,
    OutputError,
    UnsupportedFormatError,
)
from separateur_de_stems.core.models import STEM_TO_MODEL


class FakeSeparator:
    def __init__(self, outputs=None, error=None, **kwargs):
        self.kwargs = kwargs
        self.outputs = outputs or []
        self.error = error
        self.loaded = []
        self.separated = []

    def load_model(self, filename):
        self.loaded.append(filename)

    def separate(self, input_path):
        self.separated.append(input_path)
        if self.error is not None:
            raise self.error
        return list(self.outputs)


class RecordingFactory:
    def __init__(self, behavior):
        self.behavior = behavior
        self.instances = []

    def __call__(self, **kwargs):
        outputs, error = self.behavior(len(self.instances))
        separator = FakeSeparator(outputs=outputs, error=error, **kwargs)
        self.instances.append(separator)
        return separator


def make_engine(tmp_path, behavior, separator_factory):
    return SeparationEngine(
        model_dir=str(tmp_path / "models"),
        output_dir=str(tmp_path / "out"),
        separator_factory=separator_factory,
    )


def make_input(tmp_path, name="song.wav"):
    source = tmp_path / name
    source.write_bytes(b"audio")
    return str(source)


def test_engine_rejects_empty_stems_before_creating_separator(tmp_path):
    factory = RecordingFactory(lambda index: ([], None))
    engine = make_engine(tmp_path, None, factory)

    with pytest.raises(ModelUnavailableError):
        engine.run(make_input(tmp_path), set())

    assert factory.instances == []


def test_engine_rejects_missing_file(tmp_path):
    factory = RecordingFactory(lambda index: ([], None))
    engine = make_engine(tmp_path, None, factory)

    with pytest.raises(UnsupportedFormatError):
        engine.run(str(tmp_path / "missing.wav"), {"vocals"})

    assert factory.instances == []


def test_engine_rejects_directory_input(tmp_path):
    directory = tmp_path / "folder.wav"
    directory.mkdir()
    factory = RecordingFactory(lambda index: ([], None))
    engine = make_engine(tmp_path, None, factory)

    with pytest.raises(UnsupportedFormatError):
        engine.run(str(directory), {"vocals"})


def test_engine_rejects_unsupported_extension(tmp_path):
    factory = RecordingFactory(lambda index: ([], None))
    engine = make_engine(tmp_path, None, factory)

    with pytest.raises(UnsupportedFormatError):
        engine.run(make_input(tmp_path, "song.txt"), {"vocals"})


def test_engine_accepts_uppercase_extension(tmp_path):
    factory = RecordingFactory(
        lambda index: ([f"{tmp_path}/out/song_(Vocals)_x.wav"], None)
    )
    engine = make_engine(tmp_path, None, factory)

    result = engine.run(make_input(tmp_path, "song.WAV"), {"vocals"})

    assert result == {"vocals": f"{tmp_path}/out/song_(Vocals)_x.wav"}


def test_engine_cancelled_before_any_import_or_ml(tmp_path):
    factory = RecordingFactory(lambda index: ([], None))
    engine = make_engine(tmp_path, None, factory)
    cancel_event = threading.Event()
    cancel_event.set()

    with pytest.raises(CancelledError):
        engine.run(make_input(tmp_path), {"vocals"}, cancel_event=cancel_event)

    assert factory.instances == []


def test_engine_creates_output_dir(tmp_path):
    output_dir = tmp_path / "nested" / "out"
    factory = RecordingFactory(
        lambda index: ([f"{output_dir}/song_(Vocals)_x.wav"], None)
    )
    engine = SeparationEngine(
        model_dir=str(tmp_path / "models"),
        output_dir=str(output_dir),
        separator_factory=factory,
    )

    engine.run(make_input(tmp_path), {"vocals"})

    assert output_dir.is_dir()


def test_engine_raises_output_error_when_output_dir_is_file(tmp_path):
    output_dir = tmp_path / "out"
    output_dir.write_bytes(b"not a dir")
    factory = RecordingFactory(lambda index: ([], None))
    engine = SeparationEngine(
        model_dir=str(tmp_path / "models"),
        output_dir=str(output_dir),
        separator_factory=factory,
    )

    with pytest.raises(OutputError):
        engine.run(make_input(tmp_path), {"vocals"})


@pytest.mark.skipif(os.getuid() == 0, reason="root bypasses write permissions")
def test_engine_raises_output_error_when_output_dir_not_writable(tmp_path):
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    os.chmod(output_dir, 0o500)
    try:
        factory = RecordingFactory(lambda index: ([], None))
        engine = SeparationEngine(
            model_dir=str(tmp_path / "models"),
            output_dir=str(output_dir),
            separator_factory=factory,
        )

        with pytest.raises(OutputError):
            engine.run(make_input(tmp_path), {"vocals"})
    finally:
        os.chmod(output_dir, 0o600)


def test_engine_passes_exact_separator_kwargs(tmp_path):
    output_dir = tmp_path / "out"
    factory = RecordingFactory(
        lambda index: ([f"{output_dir}/song_(Vocals)_x.wav"], None)
    )
    engine = SeparationEngine(
        model_dir=str(tmp_path / "models"),
        output_dir=str(output_dir),
        log_level=logging.DEBUG,
        separator_factory=factory,
    )

    engine.run(make_input(tmp_path), {"vocals"})

    assert factory.instances[0].kwargs == {
        "model_file_dir": str(tmp_path / "models"),
        "output_dir": str(output_dir),
        "output_format": "WAV",
        "log_level": logging.DEBUG,
    }


def test_engine_loads_and_separates_with_selected_model(tmp_path):
    output_dir = tmp_path / "out"
    factory = RecordingFactory(
        lambda index: ([f"{output_dir}/song_(Vocals)_x.wav"], None)
    )
    engine = make_engine(tmp_path, None, factory)
    input_path = make_input(tmp_path)

    engine.run(input_path, {"vocals"})

    separator = factory.instances[0]
    assert separator.loaded == [STEM_TO_MODEL["vocals"]]
    assert separator.separated == [input_path]


@pytest.mark.parametrize(
    ("filename", "stem"),
    [
        ("/out/song_(Vocals)_model.wav", "vocals"),
        ("/out/song_(drumS)_model.wav", "drums"),
        ("/out/song_(Vocals).wav", "vocals"),
        ("/out/song (BASS) mix.wav", "bass"),
    ],
)
def test_engine_parses_stem_from_output_filename(tmp_path, filename, stem):
    engine = make_engine(tmp_path, None, RecordingFactory(lambda index: ([], None)))

    assert engine._stem_from_output(filename) == stem


@pytest.mark.parametrize(
    "filename",
    [
        "/out/song with (parentheses) (Vocals)_x.wav",
        "/out/other.wav",
        "/out/song_(other)_x.wav",
    ],
)
def test_engine_parsing_is_case_insensitive_and_ignores_other_parentheses(
    tmp_path, filename
):
    engine = make_engine(tmp_path, None, RecordingFactory(lambda index: ([], None)))

    expected = {"song with (parentheses) (Vocals)_x.wav": "vocals"}.get(
        Path(filename).name
    )
    assert engine._stem_from_output(filename) == expected


def test_engine_parsing_uses_last_matching_stem_over_source_parentheses(tmp_path):
    engine = make_engine(tmp_path, None, RecordingFactory(lambda index: ([], None)))

    filename = "/out/foo_(Instrumental)_x_(Vocals)_model.wav"

    assert engine._stem_from_output(filename) == "vocals"


def test_engine_resolves_relative_output_to_output_dir(tmp_path):
    output_dir = tmp_path / "out"
    factory = RecordingFactory(
        lambda index: (["song_(Vocals)_x.wav"], None)
    )
    engine = make_engine(tmp_path, None, factory)

    result = engine.run(make_input(tmp_path), {"vocals"})

    assert result == {"vocals": os.path.join(str(output_dir), "song_(Vocals)_x.wav")}


def test_engine_filters_complementary_stems(tmp_path):
    output_dir = tmp_path / "out"
    factory = RecordingFactory(
        lambda index: (
            [
                f"{output_dir}/song_(Vocals)_x.wav",
                f"{output_dir}/song_(Instrumental)_x.wav",
            ],
            None,
        )
    )
    engine = make_engine(tmp_path, None, factory)

    result = engine.run(make_input(tmp_path), {"vocals"})

    assert result == {"vocals": f"{output_dir}/song_(Vocals)_x.wav"}


def test_engine_keeps_assigned_stem_when_later_model_also_outputs_it(tmp_path):
    output_dir = tmp_path / "out"

    def behavior(index):
        if index == 0:
            return [f"{output_dir}/song_(Vocals)_first.wav"], None
        return (
            [
                f"{output_dir}/song_(Vocals)_second.wav",
                f"{output_dir}/song_(Drums)_second.wav",
            ],
            None,
        )

    factory = RecordingFactory(behavior)
    engine = make_engine(tmp_path, None, factory)

    result = engine.run(make_input(tmp_path), {"vocals", "drums"})

    assert result["vocals"] == f"{output_dir}/song_(Vocals)_first.wav"
    assert result["drums"] == f"{output_dir}/song_(Drums)_second.wav"


def test_engine_raises_when_requested_stem_is_absent_from_model_outputs(tmp_path):
    output_dir = tmp_path / "out"
    factory = RecordingFactory(
        lambda index: ([f"{output_dir}/song_(Instrumental)_x.wav"], None)
    )
    engine = make_engine(tmp_path, None, factory)

    with pytest.raises(OutputError) as exc_info:
        engine.run(make_input(tmp_path), {"vocals"})

    assert "vocals" in str(exc_info.value)


def test_engine_reports_monotonic_progress_ending_at_100(tmp_path):
    output_dir = tmp_path / "out"
    factory = RecordingFactory(
        lambda index: (
            [
                f"{output_dir}/song_(Vocals)_x.wav",
                f"{output_dir}/song_(Drums)_x.wav",
            ],
            None,
        )
    )
    engine = make_engine(tmp_path, None, factory)
    events = []

    engine.run(
        make_input(tmp_path),
        {"vocals", "drums"},
        progress_cb=lambda percent, message: events.append((percent, message)),
    )

    percents = [percent for percent, _ in events]
    assert percents == sorted(percents)
    assert all(0 <= percent <= 100 for percent in percents)
    assert percents[-1] == 100
    assert all(isinstance(message, str) for _, message in events)


def test_engine_cancels_between_models(tmp_path):
    output_dir = tmp_path / "out"
    cancel_event = threading.Event()

    def behavior(index):
        cancel_event.set()
        return [f"{output_dir}/song_(Vocals)_x.wav"], None

    factory = RecordingFactory(behavior)
    engine = make_engine(tmp_path, None, factory)

    with pytest.raises(CancelledError):
        engine.run(
            make_input(tmp_path),
            {"vocals", "drums"},
            cancel_event=cancel_event,
        )

    assert len(factory.instances) == 1


def test_engine_cancels_after_inference(tmp_path):
    output_dir = tmp_path / "out"
    cancel_event = threading.Event()

    class CancellingSeparator(FakeSeparator):
        def separate(self, input_path):
            cancel_event.set()
            return [f"{output_dir}/song_(Vocals)_x.wav"]

    created = []

    def factory(**kwargs):
        separator = CancellingSeparator(**kwargs)
        created.append(separator)
        return separator

    engine = make_engine(tmp_path, None, factory)

    with pytest.raises(CancelledError):
        engine.run(make_input(tmp_path), {"vocals"}, cancel_event=cancel_event)


def test_engine_does_not_swallow_progress_callback_exception(tmp_path):
    output_dir = tmp_path / "out"
    factory = RecordingFactory(
        lambda index: ([f"{output_dir}/song_(Vocals)_x.wav"], None)
    )
    engine = make_engine(tmp_path, None, factory)

    def exploding_callback(percent, message):
        raise ValueError("callback boom")

    with pytest.raises(ValueError, match="callback boom"):
        engine.run(make_input(tmp_path), {"vocals"}, progress_cb=exploding_callback)


def test_engine_maps_known_audio_separator_errors(tmp_path):
    from audio_separator.separator import (
        AudioExportError,
        BatchSeparationError,
        InvalidAudioDataError,
    )

    cases = [
        (InvalidAudioDataError("bad"), UnsupportedFormatError),
        (AudioExportError("export", path="x.wav", backend="ffmpeg"), OutputError),
        (BatchSeparationError([], [("x.wav", "failure")]), OutputError),
    ]
    for error, expected in cases:
        factory = RecordingFactory(lambda index, error=error: (None, error))
        engine = make_engine(tmp_path, None, factory)

        with pytest.raises(expected):
            engine.run(make_input(tmp_path), {"vocals"})


def test_engine_maps_unknown_runtime_error_to_output_error_with_filename(tmp_path):
    factory = RecordingFactory(lambda index: (None, RuntimeError("boom")))
    engine = make_engine(tmp_path, None, factory)
    input_path = make_input(tmp_path)

    with pytest.raises(OutputError) as exc_info:
        engine.run(input_path, {"vocals"})

    assert Path(input_path).name in str(exc_info.value)


def test_engine_does_not_catch_keyboard_interrupt(tmp_path):
    factory = RecordingFactory(lambda index: (None, KeyboardInterrupt()))
    engine = make_engine(tmp_path, None, factory)

    with pytest.raises(KeyboardInterrupt):
        engine.run(make_input(tmp_path), {"vocals"})
