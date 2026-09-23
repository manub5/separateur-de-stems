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

    workspace_seen = []

    def behavior(workspace, stems, progress_cb):
        workspace_seen.append(workspace)
        return {"vocals": str(external)}

    FakeEngine.behavior = staticmethod(behavior)
    monkeypatch.setattr(pipeline, "SeparationEngine", FakeEngine)

    with pytest.raises(OutputError, match="outside the private workspace"):
        pipeline.run_pipeline(
            str(source), {"vocals"}, str(output_dir), str(tmp_path / "models")
        )

    assert external.read_bytes() == b"keep"
    assert not (output_dir / "song").exists()
    assert workspace_seen and not workspace_seen[0].exists()


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


def test_pipeline_wraps_native_publication_failure_as_output_error(
    tmp_path, monkeypatch
):
    source = _source(tmp_path)
    output_dir = tmp_path / "out"
    _exporters(monkeypatch)

    def behavior(workspace, stems, progress_cb):
        vocals = workspace / "vocals.wav"
        vocals.write_bytes(b"vocals")
        return {"vocals": str(vocals)}

    def fail_publish(source_path, destination_path):
        raise OSError(18, "cross-device")

    FakeEngine.behavior = staticmethod(behavior)
    monkeypatch.setattr(pipeline, "SeparationEngine", FakeEngine)
    monkeypatch.setattr(pipeline, "_rename_no_replace", fail_publish)

    with pytest.raises(OutputError, match="publish") as exc_info:
        pipeline.run_pipeline(
            str(source), {"vocals"}, str(output_dir), str(tmp_path / "models")
        )

    assert isinstance(exc_info.value.__cause__, OSError)
    assert not (output_dir / "song").exists()


def test_terminal_progress_failure_does_not_turn_published_success_into_failure(
    tmp_path, monkeypatch
):
    source = _source(tmp_path)
    output_dir = tmp_path / "out"
    _exporters(monkeypatch)

    def behavior(workspace, stems, progress_cb):
        vocals = workspace / "vocals.wav"
        vocals.write_bytes(b"vocals")
        return {"vocals": str(vocals)}

    def progress(percent, stage):
        if percent == 100:
            raise RuntimeError("observer failed")

    FakeEngine.behavior = staticmethod(behavior)
    monkeypatch.setattr(pipeline, "SeparationEngine", FakeEngine)

    result = pipeline.run_pipeline(
        str(source),
        {"vocals"},
        str(output_dir),
        str(tmp_path / "models"),
        progress_cb=progress,
    )

    assert all(Path(path).is_file() for path in result["vocals"])


def test_pipeline_reports_ordered_export_progress_only_before_terminal_success(
    tmp_path, monkeypatch
):
    source = _source(tmp_path)
    output_dir = tmp_path / "out"
    events = []
    _exporters(monkeypatch)

    def behavior(workspace, stems, progress_cb):
        progress_cb(100, "separation.complete")
        vocals = workspace / "vocals.wav"
        vocals.write_bytes(b"vocals")
        return {"vocals": str(vocals)}

    FakeEngine.behavior = staticmethod(behavior)
    monkeypatch.setattr(pipeline, "SeparationEngine", FakeEngine)

    result = pipeline.run_pipeline(
        str(source),
        {"vocals"},
        str(output_dir),
        str(tmp_path / "models"),
        progress_cb=lambda percent, stage: events.append(
            (percent, stage, (output_dir / "song").exists())
        ),
    )

    export_events = [event for event in events if event[1].startswith("export.")]
    assert [stage for _, stage, _ in export_events] == ["export.wav", "export.mp3"]
    assert all(81 <= percent <= 99 for percent, _, _ in export_events)
    assert [percent for percent, _, _ in events] == sorted(
        percent for percent, _, _ in events
    )
    assert events[-1] == (100, "pipeline.complete", True)
    assert sum(percent == 100 for percent, _, _ in events) == 1
    assert all(Path(path).is_file() for path in result["vocals"])
