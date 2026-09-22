"""Tests for the drag and drop zone widget.

Qt runs in offscreen mode; drop events are built by hand with a ``QMimeData``
carrying local file URLs and handed straight to ``dropEvent``.
"""

from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl
from PySide6.QtGui import QDropEvent

from separateur_de_stems.ui.drop_zone import DropZone


def _drop_event(paths):
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path)) for path in paths])
    event = QDropEvent(
        QPoint(0, 0),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    event._mime = mime
    return event


def test_default_label_and_no_current_file(qtbot):
    zone = DropZone()
    qtbot.addWidget(zone)

    assert zone.current_file() is None
    assert zone.label.text() == "Drop an audio file here"


def test_set_file_stores_path_and_shows_name(qtbot):
    zone = DropZone()
    qtbot.addWidget(zone)

    zone.set_file("/x/song.wav")

    assert zone.current_file() == "/x/song.wav"
    assert "song.wav" in zone.label.text()
    assert zone.label.text() == "Selected file: song.wav"


def test_set_file_none_restores_prompt(qtbot):
    zone = DropZone()
    qtbot.addWidget(zone)

    zone.set_file("/x/song.wav")
    zone.set_file(None)

    assert zone.current_file() is None
    assert zone.label.text() == "Drop an audio file here"


def test_drop_valid_wav_emits_file_dropped(qtbot):
    zone = DropZone()
    qtbot.addWidget(zone)

    event = _drop_event(["/x/song.wav"])
    with qtbot.waitSignal(zone.fileDropped) as blocker:
        zone.dropEvent(event)

    assert blocker.args == ["/x/song.wav"]
    assert zone.current_file() == "/x/song.wav"


def test_drop_invalid_extension_emits_rejected(qtbot):
    zone = DropZone()
    qtbot.addWidget(zone)

    emitted = []
    zone.fileDropped.connect(emitted.append)
    event = _drop_event(["/x/song.ogg"])
    with qtbot.waitSignal(zone.fileRejected) as blocker:
        zone.dropEvent(event)

    assert blocker.args == ["/x/song.ogg"]
    assert emitted == []
    assert zone.current_file() is None


def test_drop_mixed_uses_first_valid(qtbot):
    zone = DropZone()
    qtbot.addWidget(zone)

    event = _drop_event(["/x/bad.ogg", "/x/good.flac"])
    with qtbot.waitSignal(zone.fileDropped) as blocker:
        zone.dropEvent(event)

    assert blocker.args == ["/x/good.flac"]
    assert zone.current_file() == "/x/good.flac"


def test_drop_uppercase_extension_is_accepted(qtbot):
    zone = DropZone()
    qtbot.addWidget(zone)

    event = _drop_event(["/x/SONG.WAV"])
    with qtbot.waitSignal(zone.fileDropped) as blocker:
        zone.dropEvent(event)

    assert blocker.args == ["/x/SONG.WAV"]
