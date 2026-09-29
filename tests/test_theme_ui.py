from types import SimpleNamespace

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPalette, QTextCursor
from PySide6.QtWidgets import QApplication, QLabel

from whisper_desk.models import Event, State
from whisper_desk.theme import DARK, LIGHT, ThemeController, resolve_theme
from whisper_desk.ui import MainWindow


def test_theme_resolution(qapp):
    palette = QPalette()
    for background, expected in (("#fafafa", LIGHT), ("#171923", DARK)):
        palette.setColor(QPalette.ColorRole.Window, QColor(background))
        assert resolve_theme(Qt.ColorScheme.Unknown, palette) == expected
    assert resolve_theme(Qt.ColorScheme.Light, palette) == LIGHT
    assert resolve_theme(Qt.ColorScheme.Dark, palette) == DARK


def test_queued_system_change_and_preview_override(qtbot, qapp):
    controller = ThemeController()
    controller.theme = LIGHT
    with qtbot.waitSignal(controller.changed):
        controller._schedule_system_change(Qt.ColorScheme.Dark)
        assert controller.theme == LIGHT
    assert controller.theme == DARK
    preview = ThemeController(override="light")
    preview.follow_scheme(Qt.ColorScheme.Dark)
    assert preview.theme == LIGHT


@pytest.mark.parametrize("state", [State.RECORDING, State.FINALIZING, State.READY, State.ERROR])
def test_theme_change_preserves_interaction(qtbot, state):
    window = MainWindow(theme="light")
    qtbot.addWidget(window)
    window.show()
    window.set_state(state)
    window.set_text("A useful thought with enough words to scroll. " * 100)
    qtbot.waitUntil(lambda: window.text.verticalScrollBar().maximum() > 0)
    cursor = window.text.textCursor()
    cursor.setPosition(3)
    cursor.setPosition(18, QTextCursor.MoveMode.KeepAnchor)
    window.text.setTextCursor(cursor)
    window.text.setFocus()
    window.text.verticalScrollBar().setValue(40)
    enabled = window.record.isEnabled(), window.copy.isEnabled(), window.clear.isEnabled()
    window.apply_theme(DARK)
    qtbot.wait(20)
    assert window.state == state
    assert window.text.textCursor().selectedText() == "seful thought w"
    assert window.text.verticalScrollBar().value() == 40
    assert window.text.hasFocus()
    assert enabled == (window.record.isEnabled(), window.copy.isEnabled(), window.clear.isEnabled())
    assert window.text.palette().color(QPalette.ColorRole.Text) == QColor(DARK.ink)


def test_circle_hit_target_and_keyboard(qtbot):
    calls = []
    service = SimpleNamespace(start=lambda: calls.append("start"), stop=lambda: calls.append("stop"), close=lambda: None)
    window = MainWindow(service, theme="dark")
    qtbot.addWidget(window)
    window.show()
    window.set_state(State.READY)
    qtbot.mouseClick(window.record, Qt.MouseButton.LeftButton, pos=QPoint(5, 5))
    assert calls == []
    qtbot.mouseClick(window.record, Qt.MouseButton.LeftButton)
    assert calls == ["start"]
    window.set_state(State.STARTING)
    assert window.record.text() == "Finish"
    window.record.setFocus()
    qtbot.keyClick(window.record, Qt.Key.Key_Space)
    assert calls == ["start", "stop"]
    window.set_state(State.FINALIZING)
    qtbot.mouseClick(window.record, Qt.MouseButton.LeftButton)
    assert calls == ["start", "stop"]


@pytest.mark.parametrize("size", [(540, 620), (440, 560)])
def test_cursor_hover_and_click_share_circle(qtbot, size):
    window = MainWindow(theme="dark")
    qtbot.addWidget(window)
    window.resize(*size)
    window.show()
    window.set_state(State.READY)
    button = window.record
    center = button.rect().center()
    radius = button.diameter // 2
    for point, inside in ((center, True), (QPoint(4, 4), False),
                          (center + QPoint(radius - 3, 0), True),
                          (center + QPoint(radius + 4, 0), False),
                          (center + QPoint(radius - 4, radius - 4), False)):
        event = QMouseEvent(QEvent.Type.MouseMove, QPointF(point), QPointF(button.mapToGlobal(point)),
                            Qt.MouseButton.NoButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(button, event)
        assert button.hitButton(point) == inside
        assert button.cursor().shape() == (Qt.CursorShape.PointingHandCursor if inside else Qt.CursorShape.ArrowCursor)
        assert button._hover_target == inside
        qtbot.waitUntil(lambda: button.hover_amount == float(inside), timeout=500)
    qtbot.mouseMove(button, center)
    window.set_state(State.FINALIZING)
    assert button.cursor().shape() == Qt.CursorShape.ArrowCursor
    assert not button._hover_target


def test_compact_notices_empty_state_and_copy_feedback(qtbot):
    window = MainWindow(theme="dark")
    qtbot.addWidget(window)
    window.resize(440, 560)
    window.show()
    window.set_state(State.READY)
    assert window.result_status.text() == "Ready for your voice"
    assert not any("One button" in label.text() for label in window.findChildren(QLabel))
    window.handle(Event("backend", ("cpu", "CUDA could not start. Using CPU. See the log for details.")))
    qtbot.wait(20)
    assert window.description.isVisible()
    assert window.empty_hint.sizeHint().height() <= window.text.viewport().height()
    window.apply_theme(LIGHT)
    assert window.description.isVisible() and window.badge.text() == "CPU • TURBO"
    window.handle(Event("final", ""))
    assert window.result_status.text() == "No speech detected"
    window.handle(Event("final", "A thought."))
    window.copy.click()
    assert window._copied and window.copy.text() == "Copied"
    window._reset_copy()
    assert not window._copied and window.copy.text() == "Copy text"


def test_animation_lifecycle(qtbot):
    window = MainWindow(theme="dark")
    qtbot.addWidget(window)
    window.show()
    window.record.motion = True
    window.set_state(State.READY)
    assert not window.record.timer.isActive() and not window.meter.timer.isActive()
    window.set_state(State.RECORDING)
    assert window.record.timer.isActive() and window.meter.timer.isActive()
    window.hide()
    assert not window.record.timer.isActive() and not window.meter.timer.isActive()
    window.record.motion = False
    window.show()
    assert not window.record.timer.isActive()
    window.set_state(State.READY)
    assert not window.meter.timer.isActive()
