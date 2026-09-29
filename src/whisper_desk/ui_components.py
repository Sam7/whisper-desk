"""Native painted surfaces and controls. No audio or inference knowledge."""
import math

from PySide6.QtCore import QEvent, QEasingCurve, QPointF, QRectF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QColor, QCursor, QFont, QIcon, QLinearGradient, QPainter, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from .models import State
from .theme import LIGHT, animations_enabled


def alpha(color, opacity):
    value = QColor(color)
    value.setAlphaF(opacity)
    return value


def draw_symbol(painter, name, rect, color):
    painter.save()
    painter.translate(rect.topLeft())
    painter.scale(rect.width() / 24, rect.height() / 24)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(color), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if name == "microphone":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(QRectF(8, 2, 8, 13), 4, 4)
        painter.setPen(QPen(QColor(color), 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(QRectF(5, 6, 14, 13), 180 * 16, 180 * 16)
        painter.drawLine(QPointF(12, 19), QPointF(12, 22))
        painter.drawLine(QPointF(8, 22), QPointF(16, 22))
    elif name == "stop":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(QRectF(5, 5, 14, 14), 3, 3)
    elif name == "copy":
        painter.drawRoundedRect(QRectF(8, 3, 12, 15), 2, 2)
        painter.drawLine(13, 3, 13, 7)
        painter.drawLine(13, 7, 17, 7)
        painter.drawRoundedRect(QRectF(4, 7, 11, 14), 2, 2)
    elif name == "check":
        painter.drawLine(5, 12, 10, 17)
        painter.drawLine(10, 17, 19, 7)
    elif name == "clear":
        painter.drawLine(5, 6, 19, 6)
        painter.drawRoundedRect(QRectF(8, 3, 8, 3), 1, 1)
        painter.drawLine(7, 6, 8, 21)
        painter.drawLine(8, 21, 16, 21)
        painter.drawLine(16, 21, 17, 6)
        painter.drawLine(10, 10, 10, 17)
        painter.drawLine(14, 10, 14, 17)
    painter.restore()


def symbol_icon(name, color):
    ratio = QApplication.instance().devicePixelRatio()
    pix = QPixmap(round(24 * ratio), round(24 * ratio))
    pix.setDevicePixelRatio(ratio)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    draw_symbol(painter, name, QRectF(0, 0, 24, 24), color)
    painter.end()
    return QIcon(pix)


class Background(QWidget):
    def __init__(self):
        super().__init__()
        self.theme = LIGHT

    def paintEvent(self, event):
        painter = QPainter(self)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor(self.theme.background[0]))
        gradient.setColorAt(1, QColor(self.theme.background[1]))
        painter.fillRect(self.rect(), gradient)
        wash = QRadialGradient(QPointF(self.width() / 2, 230), 230)
        wash.setColorAt(0, alpha(self.theme.violet[1], 0.075 if self.theme.dark else 0.025))
        wash.setColorAt(1, alpha(self.theme.violet[1], 0))
        painter.fillRect(self.rect(), wash)


class Card(QWidget):
    def __init__(self):
        super().__init__()
        self.theme = LIGHT

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        fill = QLinearGradient(0, 0, self.width(), self.height())
        fill.setColorAt(0, QColor(self.theme.card[0]))
        fill.setColorAt(1, QColor(self.theme.card[1]))
        painter.setBrush(fill)
        painter.setPen(QPen(QColor(self.theme.border), 1))
        painter.drawRoundedRect(rect, 18, 18)


class RecordButton(QPushButton):
    def __init__(self):
        super().__init__("Record")
        self.theme = LIGHT
        self.mode = State.READY
        self.diameter = 156
        self.setFixedSize(216, 216)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setMouseTracking(True)
        self._hover_target = False
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Record")
        self.motion = animations_enabled()
        self.hover_amount = 0.0
        self.press_amount = 0.0
        self.keyboard_focus = False
        self.phase = 0.0
        self.preview_hover = False
        self.preview_focus = False
        self.preview_phase = None
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(120)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.valueChanged.connect(self._hover_changed)
        self.press_animation = QVariantAnimation(self)
        self.press_animation.setDuration(70)
        self.press_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.press_animation.valueChanged.connect(self._press_changed)
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)
        self.pressed.connect(lambda: self._animate_press(1.0))
        self.released.connect(lambda: self._animate_press(0.0))

    def set_compact(self, compact):
        self.diameter = 132 if compact else 156
        self.setFixedSize(184 if compact else 216, 184 if compact else 216)
        self._sync_pointer(self.mapFromGlobal(QCursor.pos()))

    def face_rect(self):
        d = self.diameter
        return QRectF((self.width() - d) / 2, (self.height() - d) / 2, d, d)

    def hitButton(self, point):
        center = self.face_rect().center()
        return (point.x() - center.x()) ** 2 + (point.y() - center.y()) ** 2 <= (self.diameter / 2) ** 2

    def set_mode(self, state):
        self.mode = state
        self.setAccessibleName(self.text())
        self.sync_timer()
        self._sync_pointer(self.mapFromGlobal(QCursor.pos()))
        self.update()

    def sync_timer(self):
        animated = self.mode in (State.STARTING, State.RECORDING, State.LOADING, State.FINALIZING)
        visible = self.isVisible() and not self.window().isMinimized()
        if animated and visible and self.motion and self.preview_phase is None:
            self.timer.start()
        else:
            self.timer.stop()
            if not visible:
                self.animation.stop()
                self.press_animation.stop()

    def showEvent(self, event):
        super().showEvent(event)
        self.sync_timer()

    def hideEvent(self, event):
        self.timer.stop()
        self.animation.stop()
        self.press_animation.stop()
        super().hideEvent(event)

    def _tick(self):
        self.phase += 0.07
        self.update()

    def _hover_changed(self, value):
        self.hover_amount = float(value)
        self.update()

    def _press_changed(self, value):
        self.press_amount = float(value)
        self.update()

    def _animate_press(self, target):
        if not self.motion:
            self.press_amount = target
            self.update()
            return
        self.press_animation.stop()
        self.press_animation.setStartValue(self.press_amount)
        self.press_animation.setEndValue(target)
        self.press_animation.start()

    def focusInEvent(self, event):
        self.keyboard_focus = event.reason() in (Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason,
                                                 Qt.FocusReason.ShortcutFocusReason)
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event):
        self.keyboard_focus = False
        super().focusOutEvent(event)
        self.update()

    def _animate_hover(self, target):
        if not self.motion:
            self.hover_amount = target
            self.update()
            return
        self.animation.stop()
        self.animation.setStartValue(self.hover_amount)
        self.animation.setEndValue(target)
        self.animation.start()

    def enterEvent(self, event):
        self._sync_pointer(event.position().toPoint())
        super().enterEvent(event)

    def mouseMoveEvent(self, event):
        self._sync_pointer(event.position().toPoint())
        super().mouseMoveEvent(event)

    def _sync_pointer(self, point):
        inside = self.isEnabled() and self.hitButton(point)
        self.setCursor(Qt.CursorShape.PointingHandCursor if inside else Qt.CursorShape.ArrowCursor)
        if inside != self._hover_target:
            self._hover_target = inside
            self._animate_hover(float(inside))

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.EnabledChange and hasattr(self, "animation"):
            self._sync_pointer(self.mapFromGlobal(QCursor.pos()))

    def leaveEvent(self, event):
        self._sync_pointer(self.rect().topLeft())
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        face = self.face_rect()
        center = face.center()
        recording = self.mode in (State.STARTING, State.RECORDING)
        busy = self.mode in (State.LOADING, State.FINALIZING)
        colors = self.theme.rose if recording else self.theme.violet
        phase = self.phase if self.preview_phase is None else self.preview_phase
        hover = 1.0 if self.preview_hover else self.hover_amount
        press = float(self.isDown()) if self.preview_phase is not None else self.press_amount
        if not self.isEnabled():
            hover = 0
        pulse = (math.sin(phase) + 1) / 2 if recording and self.motion else 0
        painter.setPen(Qt.PenStyle.NoPen)
        glow = QRadialGradient(center + QPointF(0, 9), self.width() / 2)
        opacity = ((0.38 if self.theme.dark else 0.17) + 0.04 * hover + 0.025 * pulse) * (1 - 0.08 * press)
        glow.setColorAt(0, alpha(colors[2], opacity))
        glow.setColorAt(0.65, alpha(colors[1], opacity * 0.6))
        glow.setColorAt(1, alpha(colors[1], 0))
        painter.setBrush(glow)
        painter.drawEllipse(QRectF(self.rect()))
        ring = face.adjusted(-14, -14, 14, 14)
        ring_fill = QLinearGradient(ring.topLeft(), ring.bottomRight())
        ring_fill.setColorAt(0, alpha(colors[0], 0.17 if self.theme.dark else 0.10))
        ring_fill.setColorAt(1, alpha(colors[2], (0.34 if self.theme.dark else 0.15) + 0.02 * pulse))
        painter.setBrush(ring_fill)
        painter.setPen(QPen(alpha(colors[0], 0.25 if self.theme.dark else 0.12), 1))
        painter.drawEllipse(ring)
        if press:
            face = face.adjusted(1.6 * press, 1.6 * press, -1.6 * press, -1.6 * press)
        gradient = QLinearGradient(face.topLeft(), face.bottomRight())
        for stop, color in zip((0, 0.47, 1), colors):
            value = QColor(color)
            if not self.isEnabled() and not busy:
                value = QColor(self.theme.border)
            elif press:
                value = value.darker(round(100 + 6 * press))
            elif hover:
                value = value.lighter(round(100 + 5 * hover))
            if busy:
                value.setAlphaF(0.48 if self.theme.dark else 0.60)
            gradient.setColorAt(stop, value)
        painter.setBrush(gradient)
        painter.setPen(QPen(alpha("#ffffff", 0.64 if self.theme.dark else 0.35), 1))
        painter.drawEllipse(face)
        highlight = QRadialGradient(face.topLeft() + QPointF(face.width() * 0.25, face.height() * 0.16), face.width() * 0.78)
        highlight.setColorAt(0, alpha("#ffffff", 0.30))
        highlight.setColorAt(1, alpha("#ffffff", 0))
        painter.setBrush(highlight)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(face)
        icon_size = 40 if self.diameter == 156 else 34
        icon_rect = QRectF(center.x() - icon_size / 2, center.y() - 27, icon_size, icon_size)
        content_color = "#ffffff" if self.isEnabled() else self.theme.muted
        if busy:
            painter.setPen(QPen(QColor(content_color), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(icon_rect.adjusted(8, 8, -8, -8), int(phase * 80) * 16, 250 * 16)
        else:
            draw_symbol(painter, "stop" if recording else "microphone", icon_rect, content_color)
        font = QFont("Segoe UI")
        font.setPixelSize(17 if self.diameter == 156 else 16)
        painter.setFont(font)
        painter.setPen(QColor(content_color))
        painter.drawText(QRectF(face.left(), center.y() + 17, face.width(), 27), Qt.AlignmentFlag.AlignCenter, self.text())
        if ((self.hasFocus() and self.keyboard_focus) or self.preview_focus) and self.isEnabled():
            painter.setPen(QPen(QColor(self.theme.accent_text), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(self.face_rect().adjusted(-5, -5, 5, 5))


class Meter(QWidget):
    def __init__(self):
        super().__init__()
        self.theme = LIGHT
        self.setFixedHeight(56)
        self.level = 0.0
        self.smoothed = 0.0
        self.active = False
        self.phase = 0.0
        self.preview_phase = None
        self.motion = animations_enabled()
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.tick)

    def sync_timer(self):
        if self.active and self.isVisible() and not self.window().isMinimized() and self.preview_phase is None:
            self.timer.start()
        else:
            self.timer.stop()
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self.sync_timer()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def tick(self):
        self.phase += 0.14 if self.motion else 0
        factor = 0.6 if self.level > self.smoothed else 0.17
        self.smoothed += (self.level - self.smoothed) * factor
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        n, step, bar_width = 27, 10, 5
        x = (self.width() - (n - 1) * step - bar_width) / 2
        phase = self.phase if self.preview_phase is None else self.preview_phase
        level = self.smoothed if self.preview_phase is None else self.level
        strength = math.sqrt(min(1, max(0, level - 0.002) * 12)) if self.active else 0
        for i in range(n):
            taper = max(0, 1 - abs(i - (n - 1) / 2) / (n / 2)) ** 1.2
            wave = 0.55 + 0.45 * abs(math.sin(i * 0.67 + phase))
            # A visible resting silhouette; actual levels drive the tall bars.
            height = 5 + (8 if not self.active else 3) * taper + (self.height() - 10) * strength * taper * wave
            height = min(self.height() - 2, height)
            accent = self.theme.rose[1] if self.active else self.theme.muted
            painter.setBrush(alpha(accent, 0.4 + 0.6 * taper if self.active else 0.45))
            painter.drawRoundedRect(QRectF(x + i * step, (self.height() - height) / 2, bar_width, height), 2.5, 2.5)
