"""Check actual Windows mouse movement against the primary button's hit circle."""
import ctypes
from pathlib import Path

from PySide6.QtCore import QPoint, QTimer, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication

from whisper_desk.models import State
from whisper_desk.ui import MainWindow


def main():
    app = QApplication([])
    window = MainWindow(theme="dark")
    window.set_state(State.READY)
    window.show()
    window.raise_()
    window.activateWindow()
    original = QCursor.pos()
    set_position = ctypes.windll.user32.SetWindowPos
    set_position.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                             ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    set_position(int(window.winId()), ctypes.c_void_p(-1), 0, 0, 0, 0, 0x43)
    cases = iter(((540, 620, True), (540, 620, False), (440, 560, True), (440, 560, False)))
    checks, errors = [], []

    def move():
        try:
            width, height, inside = next(cases)
        except StopIteration:
            window.close()
            app.quit()
            return
        window.resize(width, height)
        app.processEvents()
        center = window.record.rect().center()
        point = center if inside else center + QPoint(window.record.diameter // 2 + 8, 0)
        QCursor.setPos(window.record.mapToGlobal(point))
        QTimer.singleShot(250, lambda: check(point, inside, width))

    def check(point, inside, width):
        try:
            button = window.record
            assert QApplication.widgetAt(QCursor.pos()) is button, "Test window did not receive the real pointer"
            assert button.hitButton(point) == inside
            assert button._hover_target == inside
            assert button.cursor().shape() == (Qt.CursorShape.PointingHandCursor if inside else Qt.CursorShape.ArrowCursor)
            assert button.hover_amount == float(inside)
            checks.append((width, inside))
            if inside:
                output = Path("artifacts/interaction-update")
                output.mkdir(parents=True, exist_ok=True)
                window.grab().save(str(output / f"actual-hover-{width}.png"))
        except Exception as error:
            errors.append(str(error))
            window.close()
            app.quit()
            return
        QTimer.singleShot(0, move)

    try:
        QTimer.singleShot(300, move)
        app.exec()
    finally:
        QCursor.setPos(original)
        window.close()
    if errors:
        raise SystemExit("; ".join(errors))
    print(f"Actual Windows pointer checks passed: {checks}")


if __name__ == "__main__":
    main()
