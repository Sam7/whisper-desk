"""Small shared palettes; production appearance follows Windows."""
import ctypes
from dataclasses import dataclass
import logging
import sys

from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


@dataclass(frozen=True)
class Theme:
    name: str
    background: tuple[str, str]
    card: tuple[str, str]
    ink: str
    muted: str
    border: str
    disabled: str
    badge: str
    accent_text: str
    action: str
    selection: str
    violet: tuple[str, str, str]
    rose: tuple[str, str, str]

    @property
    def dark(self):
        return self.name == "dark"


LIGHT = Theme("light", ("#fafbfe", "#f3f4fa"), ("#ffffff", "#fdfdff"),
              "#171827", "#72788c", "#e5e6ef", "#a0a5b5", "#eeebfc",
              "#6c54c7", "#efecfc", "#e0d8fb",
              ("#b7a6ff", "#8170f8", "#6552eb"), ("#eea1b0", "#d66b83", "#bb496a"))
DARK = Theme("dark", ("#1b1f2b", "#11151d"), ("#222735", "#1b202b"),
             "#f4f5fb", "#adb4cc", "#434b61", "#79829a", "#2e284b",
             "#c4b0ff", "#332d4e", "#574780",
             ("#beaeff", "#8062ff", "#5030ec"), ("#f4b0c2", "#e47796", "#bf4569"))


def resolve_theme(scheme, palette):
    if scheme == Qt.ColorScheme.Dark:
        return DARK
    if scheme == Qt.ColorScheme.Light:
        return LIGHT
    return DARK if palette.color(QPalette.ColorRole.Window).lightness() < 128 else LIGHT


def animations_enabled():
    if sys.platform != "win32":
        return True
    enabled = ctypes.c_int(1)
    ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0)
    return bool(enabled.value)


def palette_for(theme):
    palette = QPalette()
    colors = {
        QPalette.ColorRole.Window: theme.background[0], QPalette.ColorRole.WindowText: theme.ink,
        QPalette.ColorRole.Base: theme.card[0], QPalette.ColorRole.AlternateBase: theme.card[1],
        QPalette.ColorRole.Text: theme.ink, QPalette.ColorRole.Button: theme.action,
        QPalette.ColorRole.ButtonText: theme.ink, QPalette.ColorRole.Highlight: theme.selection,
        QPalette.ColorRole.HighlightedText: theme.ink, QPalette.ColorRole.PlaceholderText: theme.muted,
        QPalette.ColorRole.ToolTipBase: theme.card[0], QPalette.ColorRole.ToolTipText: theme.ink,
    }
    for role, color in colors.items():
        palette.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText, QPalette.ColorRole.WindowText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(theme.disabled))
    return palette


class ThemeController(QObject):
    changed = Signal(object)

    def __init__(self, parent=None, override=None):
        super().__init__(parent)
        if override not in (None, "light", "dark"):
            raise ValueError("Preview theme must be light or dark")
        self.override = override
        app = QApplication.instance()
        self.platform_palette = QPalette(app.palette())
        self.theme = {"light": LIGHT, "dark": DARK}.get(override) or resolve_theme(
            app.styleHints().colorScheme(), self.platform_palette)
        app.styleHints().colorSchemeChanged.connect(self._schedule_system_change)

    def _schedule_system_change(self, scheme):
        if self.override is None:
            # Qt updates its platform palette after emitting colorSchemeChanged.
            QTimer.singleShot(0, lambda: self.follow_scheme(scheme))

    def follow_scheme(self, scheme):
        if self.override is not None:
            return
        theme = resolve_theme(scheme, self.platform_palette)
        if theme != self.theme:
            self.theme = theme
            self.changed.emit(theme)


def style_native_frame(window, theme):
    if sys.platform != "win32" or QApplication.instance().platformName() == "offscreen":
        return
    value = ctypes.c_int(int(theme.dark))
    function = ctypes.windll.dwmapi.DwmSetWindowAttribute
    function.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
    function.restype = ctypes.c_long
    result = function(int(window.winId()), 20, ctypes.byref(value), ctypes.sizeof(value))
    if result:
        logging.getLogger(__name__).debug("Native frame appearance unavailable: %s", result)
