import subprocess
import sys

import pytest

from separateur_de_stems import cli
from separateur_de_stems.core.errors import CancelledError, ModelUnavailableError, OutputError


def _source(tmp_path):
    source = tmp_path / "song.wav"
    source.write_bytes(b"audio")
    return source


def test_build_parser_list_models_does_not_require_input():
    args = cli.build_parser().parse_args(["--list-models"])
    assert args.input is None
    assert args.list_models is True


def test_build_parser_defaults():
    args = cli.build_parser().parse_args(["song.wav"])
    assert args.stems == "vocals,instrumental"
    assert args.output_dir == "output"
    assert args.model_dir == "models"
    assert args.no_mp3 is False


def test_parse_stems_lowercases_trims_and_deduplicates():
    assert cli.parse_stems(" Vocals, INSTRUMENTAL ,vocals,, ") == {
        "vocals",
        "instrumental",
    }


def test_main_without_input_returns_two(capsys):
    assert cli.main([]) == 2
    assert capsys.readouterr().err


@pytest.mark.parametrize("raw_stems", ["", ",", " , ", ",,"])
def test_main_rejects_empty_stems_selection(tmp_path, monkeypatch, raw_stems):
    calls = []
    monkeypatch.setattr(cli, "run_pipeline", lambda *args, **kwargs: calls.append(args))
    assert cli.main([str(_source(tmp_path)), "--stems", raw_stems]) == 2
    assert calls == []


def test_main_rejects_unknown_stem(tmp_path, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(cli, "run_pipeline", lambda *args, **kwargs: calls.append(args))
    code = cli.main([str(_source(tmp_path)), "--stems", "vocals,saxophone"])
    assert code == 2
    assert "saxophone" in capsys.readouterr().err
    assert calls == []


def test_main_uses_pipeline_and_forwards_options(tmp_path, monkeypatch):
    source = _source(tmp_path)
    calls = []

    def fake_pipeline(input_path, stems, output_dir, model_dir, **kwargs):
        calls.append((input_path, stems, output_dir, model_dir, kwargs))
        kwargs["progress_cb"](50, "separation.running")
        return {"vocals": [str(tmp_path / "out" / "song_vocals.wav")]}

    monkeypatch.setattr(cli, "run_pipeline", fake_pipeline)
    code = cli.main(
        [
            str(source),
            "--stems",
            "Vocals,vocals",
            "--output-dir",
            str(tmp_path / "out"),
            "--model-dir",
            str(tmp_path / "models"),
            "--no-mp3",
        ]
    )
    assert code == 0
    assert calls[0][0:4] == (
        str(source),
        {"vocals"},
        str(tmp_path / "out"),
        str(tmp_path / "models"),
    )
    assert calls[0][4]["include_mp3"] is False


@pytest.mark.parametrize(
    ("error", "expected_code"),
    [(CancelledError("cancelled"), 130), (OutputError("cannot write"), 2)],
)
def test_main_maps_project_errors(tmp_path, monkeypatch, error, expected_code):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(cli, "run_pipeline", fail)
    assert cli.main([str(_source(tmp_path))]) == expected_code


def test_main_reports_progress(tmp_path, monkeypatch, capsys):
    def fake_pipeline(*args, **kwargs):
        kwargs["progress_cb"](81, "export.wav")
        return {"vocals": ["song_vocals.wav"]}

    monkeypatch.setattr(cli, "run_pipeline", fake_pipeline)
    assert cli.main([str(_source(tmp_path)), "--stems", "vocals"]) == 0
    assert "[81%] export.wav" in capsys.readouterr().out


def test_list_models_prints_canonical_stems_and_returns_zero(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "fetch_catalog",
        lambda model_dir: {"vocals_mel_band_roformer.ckpt": {"SDR": {"vocals": 12.6}}},
    )
    assert cli.main(["--list-models", "--model-dir", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert all(stem in output for stem in cli.CANONICAL_STEMS)


def test_list_models_reports_project_error_as_two(tmp_path, monkeypatch, capsys):
    def fail(model_dir):
        raise ModelUnavailableError("no catalog")

    monkeypatch.setattr(cli, "fetch_catalog", fail)
    assert cli.main(["--list-models", "--model-dir", str(tmp_path)]) == 2
    assert "no catalog" in capsys.readouterr().err


def test_main_help_returns_zero():
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--help"])
    assert exc_info.value.code == 0


def test_main_calls_ensure_bundled_ffmpeg(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(cli, "ensure_bundled_ffmpeg_on_path", lambda: calls.append(True))
    monkeypatch.setattr(cli, "fetch_catalog", lambda model_dir: {})
    cli.main(["--list-models", "--model-dir", str(tmp_path)])
    assert calls == [True]


def test_no_qt_import():
    code = (
        "import sys; import separateur_de_stems.cli; "
        "assert 'PySide6' not in sys.modules, 'cli imported Qt'"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True)
    assert result.returncode == 0, result.stderr.decode()
