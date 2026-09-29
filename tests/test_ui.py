from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from whisper_desk.models import Event, State
from whisper_desk.ui import MainWindow


def test_empty_result_copy_clear(qtbot):
    w = MainWindow()
    qtbot.addWidget(w)
    w.show()
    w.set_state(State.READY)
    assert not w.copy.isEnabled() and not w.clear.isEnabled()
    assert w.empty_hint.isVisible()
    w.handle(Event("final", "A real thought."))
    assert w.copy.isEnabled() and w.clear.isEnabled()
    assert not w.empty_hint.isVisible()
    qtbot.mouseClick(w.copy, Qt.MouseButton.LeftButton)
    assert QApplication.clipboard().text() == "A real thought."
    qtbot.mouseClick(w.clear, Qt.MouseButton.LeftButton)
    assert w.text.toPlainText() == ""


def test_recording_finalizing_error_and_wrapping(qtbot):
    w = MainWindow()
    qtbot.addWidget(w)
    w.resize(440, 540)
    w.show()
    w.set_state(State.RECORDING)
    w.set_text("A sentence with enough words to wrap naturally. " * 100)
    assert w.record.text() == "Finish" and not w.clear.isEnabled()
    w.set_state(State.FINALIZING)
    assert not w.record.isEnabled() and w.copy.isEnabled()
    w.handle(Event("error", "Microphone unavailable. Check Windows microphone access and your input device."))
    w.set_state(State.ERROR)
    assert w.description.wordWrap()
    assert w.text.toPlainText().startswith("A sentence")
