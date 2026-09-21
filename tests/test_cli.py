import argparse

import pytest

from separateur_de_stems import cli
from separateur_de_stems.core.errors import (
    CancelledError,
    ModelUnavailableError,
    OutputError,
)


class RecordingExport:
    def __init__(self):
        self.wav_calls = []
        self.mp3_calls = []

    def to_wav24(self, src, dest):
        self.wav_calls.append((src, dest))
        with open(dest, "wb") as handle:
            handle.write(b"wav24")
        return dest

    def to_mp3_320(self, src, dest):
        self.mp3_calls.append((src, dest))
        with open(dest, "wb") as handle:
            handle.write(b"mp3")
        return dest


def make_engine_factory(outputs_by_input, engine_factory=None):
    class FakeEngine:
        def __init__(self, model_dir, output_dir):
            self.model_dir = model_dir
            self.output_dir = output_dir
            self.calls = []

        def run(
            self,
            input_path,
            stems,
            progress_cb=None,
            cancel_event=None,
        ):
            self.calls.append((input_path, stems, cancel_event))
            if progress_cb is not None:
                progress_cb(50, "halfway")
            return dict(outputs_by_input[input_path])

    def factory(model_dir, output_dir):
        engine = FakeEngine(model_dir, output_dir)
        factory.instances.append(engine)
        return engine

    factory.instances = []
    return factory


def test_build_parser_list_models_does_not_require_input():
    parser = cli.build_parser()

    args = parser.parse_args(["--list-models"])

    assert args.input is None
    assert args.list_models is True


def test_build_parser_input_is_optional():
    parser = cli.build_parser()

    args = parser.parse_args(["song.wav"])

    assert args.input == "song.wav"
    assert args.list_models is False


def test_build_parser_defaults():
    parser = cli.build_parser()

    args = parser.parse_args(["song.wav"])

    assert args.stems == "vocals,instrumental"
    assert args.output_dir == "output"
    assert args.model_dir == "models"
    assert args.no_mp3 is False


def test_parse_stems_lowercases_trims_and_deduplicates():
    assert cli.parse_stems(" Vocals, INSTRUMENTAL ,vocals,, ") == {
        "vocals",
        "instrumental",
    }


def test_main_stems_are_lowercased_and_deduplicated(tmp_path, monkeypatch):
    source = tmp_path / "song.wav"
    source.write_bytes(b"audio")
    intermediate = tmp_path / "engine_out" / "song_(Vocals)_model.wav"
    intermediate.parent.mkdir()
    intermediate.write_bytes(b"intermediate")
    factory = make_engine_factory({str(source): {"vocals": str(intermediate)}})
    exporter = RecordingExport()
    monkeypatch.setattr(cli, "SeparationEngine", factory)
    monkeypatch.setattr(cli, "to_wav24", exporter.to_wav24)
    monkeypatch.setattr(cli, "to_mp3_320", exporter.to_mp3_320)

    code = cli.main(
        [
            str(source),
            "--stems",
            "Vocals, vocals ,VOCALS",
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )

    assert code == 0
    _, stems, _ = factory.instances[0].calls[0]
    assert stems == {"vocals"}
    assert exporter.wav_calls == [
        (str(intermediate), str(tmp_path / "out" / "song_vocals.wav"))
    ]


def test_main_without_input_returns_two(tmp_path, capsys):
    code = cli.main(["--model-dir", str(tmp_path), "--output-dir", str(tmp_path)])

    assert code == 2
    assert capsys.readouterr().err.strip() != ""


def test_main_rejects_unknown_stem(tmp_path, capsys, monkeypatch):
    source = tmp_path / "song.wav"
    source.write_bytes(b"audio")
    factory = make_engine_factory({str(source): {}})
    monkeypatch.setattr(cli, "SeparationEngine", factory)

    code = cli.main(
        [
            str(source),
            "--stems",
            "vocals,saxophone",
            "--model-dir",
            str(tmp_path),
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert code == 2
    assert "saxophone" in capsys.readouterr().err
    assert factory.instances == []


def test_main_success_exports_wav_and_mp3_with_expected_names(tmp_path, monkeypatch):
    source = tmp_path / "song.wav"
    source.write_bytes(b"audio")
    intermediate = tmp_path / "engine_out" / "song_(Vocals)_model.wav"
    intermediate.parent.mkdir()
    intermediate.write_bytes(b"intermediate")
    factory = make_engine_factory({str(source): {"vocals": str(intermediate)}})
    exporter = RecordingExport()
    monkeypatch.setattr(cli, "SeparationEngine", factory)
    monkeypatch.setattr(cli, "to_wav24", exporter.to_wav24)
    monkeypatch.setattr(cli, "to_mp3_320", exporter.to_mp3_320)

    code = cli.main(
        [
            str(source),
            "--stems",
            "vocals",
            "--model-dir",
            str(tmp_path / "models"),
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )

    expected_wav = tmp_path / "out" / "song_vocals.wav"
    expected_mp3 = tmp_path / "out" / "song_vocals.mp3"
    assert code == 0
    assert exporter.wav_calls == [(str(intermediate), str(expected_wav))]
    assert exporter.mp3_calls == [(str(expected_wav), str(expected_mp3))]
    assert expected_wav.exists()
    assert expected_mp3.exists()
    assert factory.instances[0].model_dir == str(tmp_path / "models")
    assert factory.instances[0].output_dir == str(tmp_path / "out")


def test_main_no_mp3_skips_mp3_export(tmp_path, monkeypatch):
    source = tmp_path / "song.wav"
    source.write_bytes(b"audio")
    intermediate = tmp_path / "engine_out" / "song_(Vocals)_model.wav"
    intermediate.parent.mkdir()
    intermediate.write_bytes(b"intermediate")
    factory = make_engine_factory({str(source): {"vocals": str(intermediate)}})
    exporter = RecordingExport()
    monkeypatch.setattr(cli, "SeparationEngine", factory)
    monkeypatch.setattr(cli, "to_wav24", exporter.to_wav24)
    monkeypatch.setattr(cli, "to_mp3_320", exporter.to_mp3_320)

    code = cli.main(
        [
            str(source),
            "--stems",
            "vocals",
            "--no-mp3",
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )

    assert code == 0
    assert exporter.mp3_calls == []


def test_main_removes_intermediate_engine_wavs(tmp_path, monkeypatch):
    source = tmp_path / "song.wav"
    source.write_bytes(b"audio")
    intermediate = tmp_path / "engine_out" / "song_(Vocals)_model.wav"
    intermediate.parent.mkdir()
    intermediate.write_bytes(b"intermediate")
    factory = make_engine_factory({str(source): {"vocals": str(intermediate)}})
    exporter = RecordingExport()
    monkeypatch.setattr(cli, "SeparationEngine", factory)
    monkeypatch.setattr(cli, "to_wav24", exporter.to_wav24)
    monkeypatch.setattr(cli, "to_mp3_320", exporter.to_mp3_320)

    cli.main(
        [
            str(source),
            "--stems",
            "vocals",
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )

    assert not intermediate.exists()


def test_main_never_deletes_preexisting_file(tmp_path, monkeypatch):
    source = tmp_path / "song.wav"
    source.write_bytes(b"audio")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    preexisting = out_dir / "song_vocals.wav"
    preexisting.write_bytes(b"keep me")
    intermediate = tmp_path / "engine_out" / "song_(Vocals)_model.wav"
    intermediate.parent.mkdir()
    intermediate.write_bytes(b"intermediate")
    factory = make_engine_factory({str(source): {"vocals": str(intermediate)}})
    exporter = RecordingExport()
    monkeypatch.setattr(cli, "SeparationEngine", factory)
    monkeypatch.setattr(cli, "to_wav24", exporter.to_wav24)
    monkeypatch.setattr(cli, "to_mp3_320", exporter.to_mp3_320)

    cli.main(
        [
            str(source),
            "--stems",
            "vocals",
            "--output-dir",
            str(out_dir),
        ]
    )

    assert preexisting.exists()
    assert preexisting.read_bytes() == b"keep me"


def test_main_refuses_intermediate_equal_to_wav_target(tmp_path, monkeypatch, capsys):
    source = tmp_path / "song.wav"
    source.write_bytes(b"audio")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    target = out_dir / "song_vocals.wav"
    target.write_bytes(b"engine output")
    factory = make_engine_factory({str(source): {"vocals": str(target)}})
    exporter = RecordingExport()
    monkeypatch.setattr(cli, "SeparationEngine", factory)
    monkeypatch.setattr(cli, "to_wav24", exporter.to_wav24)
    monkeypatch.setattr(cli, "to_mp3_320", exporter.to_mp3_320)

    code = cli.main(
        [
            str(source),
            "--stems",
            "vocals",
            "--no-mp3",
            "--output-dir",
            str(out_dir),
        ]
    )

    assert code == 2
    assert exporter.wav_calls == []
    assert target.read_bytes() == b"engine output"
    assert capsys.readouterr().err.strip() != ""


def test_main_refuses_intermediate_symlink_to_wav_target(tmp_path, monkeypatch, capsys):
    source = tmp_path / "song.wav"
    source.write_bytes(b"audio")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    target = out_dir / "song_vocals.wav"
    target.write_bytes(b"engine output")
    link = tmp_path / "engine_out" / "song_(Vocals)_model.wav"
    link.parent.mkdir()
    link.symlink_to(target)
    factory = make_engine_factory({str(source): {"vocals": str(link)}})
    exporter = RecordingExport()
    monkeypatch.setattr(cli, "SeparationEngine", factory)
    monkeypatch.setattr(cli, "to_wav24", exporter.to_wav24)
    monkeypatch.setattr(cli, "to_mp3_320", exporter.to_mp3_320)

    code = cli.main(
        [
            str(source),
            "--stems",
            "vocals",
            "--no-mp3",
            "--output-dir",
            str(out_dir),
        ]
    )

    assert code == 2
    assert exporter.wav_calls == []
    assert target.read_bytes() == b"engine output"
    assert capsys.readouterr().err.strip() != ""


def test_main_does_not_delete_symlink_target(tmp_path, monkeypatch):
    source = tmp_path / "song.wav"
    source.write_bytes(b"audio")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    preexisting = out_dir / "keep.wav"
    preexisting.write_bytes(b"keep me")
    link = tmp_path / "engine_out" / "song_(Vocals)_model.wav"
    link.parent.mkdir()
    link.symlink_to(preexisting)
    factory = make_engine_factory({str(source): {"vocals": str(link)}})
    exporter = RecordingExport()
    monkeypatch.setattr(cli, "SeparationEngine", factory)
    monkeypatch.setattr(cli, "to_wav24", exporter.to_wav24)
    monkeypatch.setattr(cli, "to_mp3_320", exporter.to_mp3_320)

    code = cli.main(
        [
            str(source),
            "--stems",
            "vocals",
            "--no-mp3",
            "--output-dir",
            str(out_dir),
        ]
    )

    assert code == 0
    assert preexisting.exists()
    assert preexisting.read_bytes() == b"keep me"
    assert not link.exists()


def test_main_never_deletes_file_outside_run(tmp_path, monkeypatch):
    source = tmp_path / "song.wav"
    source.write_bytes(b"audio")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    unrelated = out_dir / "unrelated.wav"
    unrelated.write_bytes(b"unrelated")
    intermediate = tmp_path / "engine_out" / "song_(Vocals)_model.wav"
    intermediate.parent.mkdir()
    intermediate.write_bytes(b"intermediate")
    factory = make_engine_factory({str(source): {"vocals": str(intermediate)}})
    exporter = RecordingExport()
    monkeypatch.setattr(cli, "SeparationEngine", factory)
    monkeypatch.setattr(cli, "to_wav24", exporter.to_wav24)
    monkeypatch.setattr(cli, "to_mp3_320", exporter.to_mp3_320)

    cli.main(
        [
            str(source),
            "--stems",
            "vocals",
            "--no-mp3",
            "--output-dir",
            str(out_dir),
        ]
    )

    assert unrelated.exists()
    assert unrelated.read_bytes() == b"unrelated"
    assert not intermediate.exists()


@pytest.mark.parametrize("raw_stems", ["", ",", " , ", ",,"])
def test_main_rejects_empty_stems_selection(tmp_path, monkeypatch, capsys, raw_stems):
    source = tmp_path / "song.wav"
    source.write_bytes(b"audio")
    factory = make_engine_factory({str(source): {}})
    monkeypatch.setattr(cli, "SeparationEngine", factory)

    code = cli.main(
        [
            str(source),
            "--stems",
            raw_stems,
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )

    assert code == 2
    assert factory.instances == []
    assert capsys.readouterr().err.strip() != ""


def test_main_reports_progress(tmp_path, monkeypatch, capsys):
    source = tmp_path / "song.wav"
    source.write_bytes(b"audio")
    intermediate = tmp_path / "engine_out" / "song_(Vocals)_model.wav"
    intermediate.parent.mkdir()
    intermediate.write_bytes(b"intermediate")
    factory = make_engine_factory({str(source): {"vocals": str(intermediate)}})
    exporter = RecordingExport()
    monkeypatch.setattr(cli, "SeparationEngine", factory)
    monkeypatch.setattr(cli, "to_wav24", exporter.to_wav24)
    monkeypatch.setattr(cli, "to_mp3_320", exporter.to_mp3_320)

    cli.main(
        [
            str(source),
            "--stems",
            "vocals",
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )

    assert "[50%] halfway" in capsys.readouterr().out


def test_main_cancelled_returns_130(tmp_path, monkeypatch):
    source = tmp_path / "song.wav"
    source.write_bytes(b"audio")

    class CancellingEngine:
        def __init__(self, model_dir, output_dir):
            pass

        def run(self, input_path, stems, progress_cb=None, cancel_event=None):
            raise CancelledError("cancelled")

    monkeypatch.setattr(cli, "SeparationEngine", CancellingEngine)

    code = cli.main([str(source), "--output-dir", str(tmp_path / "out")])

    assert code == 130


def test_main_output_error_returns_two(tmp_path, monkeypatch, capsys):
    source = tmp_path / "song.wav"
    source.write_bytes(b"audio")

    class FailingEngine:
        def __init__(self, model_dir, output_dir):
            pass

        def run(self, input_path, stems, progress_cb=None, cancel_event=None):
            raise OutputError("cannot write")

    monkeypatch.setattr(cli, "SeparationEngine", FailingEngine)

    code = cli.main([str(source), "--output-dir", str(tmp_path / "out")])

    assert code == 2
    assert "cannot write" in capsys.readouterr().err


def test_main_export_error_is_not_swallowed(tmp_path, monkeypatch, capsys):
    source = tmp_path / "song.wav"
    source.write_bytes(b"audio")
    intermediate = tmp_path / "engine_out" / "song_(Vocals)_model.wav"
    intermediate.parent.mkdir()
    intermediate.write_bytes(b"intermediate")
    factory = make_engine_factory({str(source): {"vocals": str(intermediate)}})
    monkeypatch.setattr(cli, "SeparationEngine", factory)

    def failing_wav24(src, dest):
        raise OutputError("ffmpeg boom")

    monkeypatch.setattr(cli, "to_wav24", failing_wav24)

    code = cli.main(
        [str(source), "--stems", "vocals", "--output-dir", str(tmp_path / "out")]
    )

    assert code == 2
    assert "ffmpeg boom" in capsys.readouterr().err


def test_main_export_failure_keeps_intermediate_wav(tmp_path, monkeypatch):
    source = tmp_path / "song.wav"
    source.write_bytes(b"audio")
    intermediate = tmp_path / "engine_out" / "song_(Vocals)_model.wav"
    intermediate.parent.mkdir()
    intermediate.write_bytes(b"intermediate")
    factory = make_engine_factory({str(source): {"vocals": str(intermediate)}})
    monkeypatch.setattr(cli, "SeparationEngine", factory)

    def failing_wav24(src, dest):
        raise OutputError("boom")

    monkeypatch.setattr(cli, "to_wav24", failing_wav24)

    cli.main(
        [str(source), "--stems", "vocals", "--output-dir", str(tmp_path / "out")]
    )

    assert intermediate.exists()


def test_list_models_prints_canonical_stems_and_returns_zero(
    tmp_path, monkeypatch, capsys
):
    catalog = {"vocals_mel_band_roformer.ckpt": {"SDR": {"vocals": 12.6}}}
    received = []

    def fake_fetch_catalog(model_dir):
        received.append(model_dir)
        return catalog

    monkeypatch.setattr(cli, "fetch_catalog", fake_fetch_catalog)

    code = cli.main(["--list-models", "--model-dir", str(tmp_path / "models")])

    out = capsys.readouterr().out
    assert code == 0
    assert received == [str(tmp_path / "models")]
    for stem in cli.CANONICAL_STEMS:
        assert stem in out


def test_list_models_reports_project_error_as_two(tmp_path, monkeypatch, capsys):
    def failing_fetch_catalog(model_dir):
        raise ModelUnavailableError("no catalog")

    monkeypatch.setattr(cli, "fetch_catalog", failing_fetch_catalog)

    code = cli.main(["--list-models", "--model-dir", str(tmp_path)])

    assert code == 2
    assert "no catalog" in capsys.readouterr().err


def test_list_models_reports_unexpected_error_as_two_without_traceback(
    tmp_path, monkeypatch, capsys
):
    def failing_fetch_catalog(model_dir):
        raise RuntimeError("network down")

    monkeypatch.setattr(cli, "fetch_catalog", failing_fetch_catalog)

    code = cli.main(["--list-models", "--model-dir", str(tmp_path)])

    captured = capsys.readouterr()
    assert code == 2
    assert captured.err.strip() != ""
    assert "Traceback" not in captured.err


def test_main_missing_output_file_returns_two(tmp_path, monkeypatch, capsys):
    source = tmp_path / "song.wav"
    source.write_bytes(b"audio")
    missing = tmp_path / "engine_out" / "song_(Vocals)_model.wav"
    factory = make_engine_factory({str(source): {"vocals": str(missing)}})
    monkeypatch.setattr(cli, "SeparationEngine", factory)

    code = cli.main(
        [str(source), "--stems", "vocals", "--output-dir", str(tmp_path / "out")]
    )

    captured = capsys.readouterr()
    assert code == 2
    assert "vocals" in captured.err
    assert "Traceback" not in captured.err


def test_main_help_returns_zero():
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--help"])

    assert exc_info.value.code == 0


def test_build_parser_accepts_argv_none(monkeypatch):
    monkeypatch.setattr("sys.argv", ["separateur-de-stems", "--list-models"])

    code = cli.main(None)

    assert code == 0


def test_no_qt_import():
    import sys

    assert "PySide6" not in sys.modules
