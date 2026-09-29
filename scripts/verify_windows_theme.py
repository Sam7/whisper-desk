"""Bounded Windows appearance smoke test; restores the original registry value."""
import ctypes
import json
from pathlib import Path
import winreg

from PySide6.QtCore import QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication

from whisper_desk.models import State
from whisper_desk.ui import MainWindow
from capture_native import capture_window

KEY = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
OUTPUT = Path("artifacts/windows-theme")


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    app.setStyle("Fusion")
    window = MainWindow()
    window.set_state(State.RECORDING)
    window.set_text("Keep this selected thought while Windows changes appearance.")
    cursor = window.text.textCursor()
    cursor.setPosition(5)
    cursor.setPosition(18, QTextCursor.MoveMode.KeepAnchor)
    window.text.setTextCursor(cursor)
    window.show()
    reports, errors = [], []
    changes = iter((1, 0))
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY, 0, winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE)
    try:
        original, kind = winreg.QueryValueEx(key, "AppsUseLightTheme")
    except FileNotFoundError:
        original, kind = None, winreg.REG_DWORD
    broadcast = ctypes.windll.user32.SendMessageTimeoutW
    broadcast.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_void_p,
                          ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p]

    def notify():
        setting = ctypes.create_unicode_buffer("ImmersiveColorSet")
        broadcast(0xffff, 0x1A, 0, ctypes.cast(setting, ctypes.c_void_p), 2, 100, None)

    def next_theme():
        try:
            value = next(changes)
        except StopIteration:
            window.close()
            app.quit()
            return
        winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, value)
        notify()
        QTimer.singleShot(1200, lambda: capture(value))

    def capture(value):
        try:
            expected = "light" if value else "dark"
            assert window.theme.name == expected, (expected, window.theme.name)
            assert window.state == State.RECORDING and window.record.text() == "Finish"
            assert window.text.textCursor().selectedText() == "this selected"
            native = ctypes.c_int()
            get = ctypes.windll.dwmapi.DwmGetWindowAttribute
            get.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
            result = get(int(window.winId()), 20, ctypes.byref(native), ctypes.sizeof(native))
            assert result == 0 and native.value == int(not value)
            window.grab().save(str(OUTPUT / f"{expected}.png"))
            capture_window(int(window.winId()), OUTPUT / f"{expected}-native-frame.png")
            reports.append({"theme": expected, "state": window.state, "native_dark_frame": native.value,
                            "selection": window.text.textCursor().selectedText()})
        except Exception as error:
            errors.append(str(error))
            window.close()
            app.quit()
            return
        QTimer.singleShot(0, next_theme)

    try:
        QTimer.singleShot(250, next_theme)
        app.exec()
    finally:
        if original is None:
            winreg.DeleteValue(key, "AppsUseLightTheme")
        else:
            winreg.SetValueEx(key, "AppsUseLightTheme", 0, kind, original)
        notify()
        key.Close()
    (OUTPUT / "report.json").write_text(json.dumps({"checks": reports, "errors": errors,
                                                   "original_restored": True}, indent=2, default=str))
    if errors:
        raise SystemExit("; ".join(errors))
    print("Windows light/dark changes and native titlebars verified; original setting restored.")


if __name__ == "__main__":
    main()
