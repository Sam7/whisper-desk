from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from whisper_desk.models import Event, State
from whisper_desk.ui import Bridge, MainWindow


def begin(window):
    window.set_state(State.STARTING)
    window.handle(Event("text", ""))
    window.set_state(State.RECORDING)


def finish(window, text):
    window.set_state(State.FINALIZING)
    window.handle(Event("text", text))
    window.handle(Event("final", text))
    window.set_state(State.READY)


def test_revisions_and_new_recordings_preserve_history_until_clear(qtbot):
    window = MainWindow(theme="dark")
    qtbot.addWidget(window)
    window.show()
    window.set_state(State.READY)
    begin(window)
    finish(window, "The first thought.")
    begin(window)
    assert window.text.toPlainText() == "The first thought."
    window.handle(Event("text", "A second"))
    assert window.text.toPlainText() == "The first thought.\n\nA second"
    window.handle(Event("text", "The second thought."))
    finish(window, "The second thought.")
    expected = "The first thought.\n\nThe second thought."
    assert window.text.toPlainText() == expected
    window.copy.click()
    assert QApplication.clipboard().text() == expected
    begin(window)
    finish(window, "")
    assert window.text.toPlainText() == expected
    assert window.result_status.text() == "No speech detected"
    window.clear.click()
    assert window.text.toPlainText() == ""
    begin(window)
    finish(window, "A fresh start.")
    assert window.text.toPlainText() == "A fresh start."


def test_failed_recording_and_retry_keep_visible_words(qtbot):
    window = MainWindow(theme="light")
    qtbot.addWidget(window)
    window.show()
    window.set_state(State.READY)
    begin(window)
    finish(window, "Completed words.")
    begin(window)
    window.handle(Event("text", "Partial words"))
    window.handle(Event("error", "Microphone disconnected."))
    window.set_state(State.ERROR)
    preserved = "Completed words.\n\nPartial words"
    assert window.text.toPlainText() == preserved
    begin(window)
    window.set_state(State.STARTING)  # Repeated presentation must not duplicate the prefix.
    window.handle(Event("text", ""))
    finish(window, "Recovered words.")
    assert window.text.toPlainText() == preserved + "\n\nRecovered words."


def test_new_recording_and_final_keep_scroll_at_bottom(qtbot):
    window = MainWindow(theme="dark")
    qtbot.addWidget(window)
    window.show()
    window.set_state(State.READY)
    window.set_text("An earlier paragraph.\n" * 30)
    window.text.verticalScrollBar().setValue(0)
    begin(window)
    window.handle(Event("text", "More words. " * 15))
    finish(window, "More words. " * 16)
    scrollbar = window.text.verticalScrollBar()
    assert scrollbar.value() == scrollbar.maximum()
    assert window.text.toPlainText().startswith("An earlier paragraph.")

