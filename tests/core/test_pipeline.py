from pathlib import Path

import pytest

from separateur_de_stems.core.errors import OutputError
from separateur_de_stems.core import pipeline


class FakeEngine:
    behavior = None

    def __init__(self, model_dir, output_dir):
        self.output_dir = Path(output_dir)

    def run(self, input_path, stems, progress_cb=None):
        return self.behavior(self.output_dir, stems, progress_cb)


def _source(tmp_path):
    source = tmp_path / "song.wav"
    source.write_bytes(b"audio")
    return source


def _exporters(monkeypatch):
    def export(src, dest, **kwargs):
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(Path(src).read_bytes())
        return dest

    monkeypatch.setattr(pipeline, "to_wav24", export)
    monkeypatch.setattr(pipeline, "to_mp3_320", export)


def test_pipeline_publishes_every_requested_stem_and_cleans_auxiliary_outputs(
    tmp_path, monkeypatch
):
    source = _source(tmp_path)
    output_dir = tmp_path / "out"
    _exporters(monkeypatch)

    def behavior(workspace, stems, progress_cb):
        vocals = workspace / "song_(Vocals)_model.wav"
        auxiliary = workspace / "song_(Instrumental)_model.wav"
        vocals.write_bytes(b"vocals")
        auxiliary.write_bytes(b"auxiliary")
        return {"vocals": str(vocals)}

    FakeEngine.behavior = staticmethod(behavior)
    monkeypatch.setattr(pipeline, "SeparationEngine", FakeEngine)

    result = pipeline.run_pipeline(
        str(source), {"vocals"}, str(output_dir), str(tmp_path / "models")
    )

    assert set(result) == {"vocals"}
    assert len(result["vocals"]) == 2
    assert all(Path(path).is_file() for path in result["vocals"])
    assert not list(output_dir.glob(".stem-run-*"))


def test_pipeline_partial_failure_publishes_nothing_and_preserves_external_path(
    tmp_path, monkeypatch
):
    source = _source(tmp_path)
    output_dir = tmp_path / "out"
    external = tmp_path / "external.wav"
    external.write_bytes(b"keep")

    def behavior(workspace, stems, progress_cb):
        partial = workspace / "partial.wav"
        partial.write_bytes(b"partial")
        raise OutputError("second model failed")

    FakeEngine.behavior = staticmethod(behavior)
    monkeypatch.setattr(pipeline, "SeparationEngine", FakeEngine)

    with pytest.raises(OutputError, match="second model failed"):
        pipeline.run_pipeline(
            str(source), {"vocals", "drums"}, str(output_dir), str(tmp_path / "models")
        )

    assert external.read_bytes() == b"keep"
    assert not (output_dir / "song").exists()
    assert not list(output_dir.glob(".stem-run-*"))


def test_pipeline_rejects_external_workspace_without_deleting_it(tmp_path):
    source = _source(tmp_path)
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    external = tmp_path / ".stem-separator-external"
    external.mkdir()
    marker = external / "keep.txt"
    marker.write_text("keep")

    with pytest.raises(OutputError, match="workspace"):
        pipeline.run_pipeline(
            str(source),
            {"vocals"},
            str(output_dir),
            str(tmp_path / "models"),
            _workspace=str(external),
        )

    assert marker.read_text() == "keep"


def test_pipeline_rejects_incomplete_result_and_reserves_progress_for_export(
    tmp_path, monkeypatch
):
    source = _source(tmp_path)
    output_dir = tmp_path / "out"
    events = []

    def behavior(workspace, stems, progress_cb):
        progress_cb(100, "separation.complete")
        vocals = workspace / "vocals.wav"
        vocals.write_bytes(b"vocals")
        return {"vocals": str(vocals)}

    FakeEngine.behavior = staticmethod(behavior)
    monkeypatch.setattr(pipeline, "SeparationEngine", FakeEngine)

    with pytest.raises(OutputError, match="drums"):
        pipeline.run_pipeline(
            str(source),
            {"vocals", "drums"},
            str(output_dir),
            str(tmp_path / "models"),
            progress_cb=lambda percent, stage: events.append((percent, stage)),
        )

    assert events[-1][0] <= 80
    assert not (output_dir / "song").exists()
