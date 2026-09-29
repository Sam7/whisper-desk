"""Window composition and presentation state; workers remain behind events."""
from PySide6.QtCore import QEvent, QObject, QSize, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QFont, QTextBlockFormat, QTextCursor
from PySide6.QtWidgets import (QApplication, QFrame, QGraphicsDropShadowEffect, QHBoxLayout,
                              QLabel, QMainWindow, QPushButton, QSizePolicy, QTextEdit, QVBoxLayout, QWidget)

from .branding import application_icon
from .models import Event, State
from .theme import ThemeController, palette_for, style_native_frame
from .ui_components import Background, Card, Meter, RecordButton, symbol_icon


class Bridge(QObject):
    event = Signal(object)


class Header(QWidget):
    def __init__(self):
        super().__init__()
        self.title = QLabel("Whisper Desk", self)
        self.title.setObjectName("brand")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle = QLabel("A little space for your thoughts.", self)
        self.subtitle.setObjectName("subtitle")
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge = QLabel("LOCAL • TURBO", self)
        self.badge.setObjectName("badge")
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.compact = False
        self.setFixedHeight(76)

    def arrange(self, compact):
        self.compact = compact
        self.setFixedHeight(96 if compact else 76)
        self.position()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.position()

    def position(self):
        width = self.width()
        font = QFont("Segoe UI")
        font.setPixelSize(30 if self.compact else 34)
        font.setWeight(QFont.Weight.Medium)
        self.title.setFont(font)
        self.title.setStyleSheet(f"font-size: {30 if self.compact else 34}px; font-weight: 500;")
        self.title.setGeometry(0, 0, width, 43)
        self.subtitle.setGeometry(0, 46, width, 22)
        badge_width = self.badge.sizeHint().width()
        self.badge.setGeometry((width - badge_width) // 2 if self.compact else width - badge_width,
                               72 if self.compact else 1, badge_width, 25)


class MainWindow(QMainWindow):
    def __init__(self, service=None, *, theme=None):
        super().__init__()
        self.service = service
        self.state = State.LOADING
        self.backend = "LOCAL • TURBO"
        self.backend_notice = ""
        self.error_message = ""
        self.seconds = 0.0
        self.final_status = "Ready for your voice"
        self._copied = False
        self._recording_prefix = ""
        self._setting_text = False
        self.setWindowTitle("Whisper Desk")
        self.setWindowIcon(application_icon())
        self.resize(540, 770)
        self.setMinimumSize(440, 560)
        self.root = Background()
        self.setCentralWidget(self.root)
        self.layout = QVBoxLayout(self.root)
        self.layout.setSpacing(0)
        self.header = Header()
        self.badge = self.header.badge
        self.layout.addWidget(self.header)
        self.hero_gap = self.layout.count()
        self.layout.addSpacing(14)
        self.hero = QWidget(self.root)
        self.hero.installEventFilter(self)
        self.record = RecordButton()
        self.record.setParent(self.hero)
        self.record.show()
        self.record.clicked.connect(self.toggle)
        self.meter = Meter()
        self.meter.setParent(self.hero)
        self.meter.show()
        self.meter.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.layout.addWidget(self.hero)
        self.layout.addSpacing(4)
        self.time_label = QLabel("Audio stays on this computer")
        self.time_label.setObjectName("caption")
        self.time_label.setFixedHeight(18)
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.time_label)
        self.description = QLabel()
        self.description.setObjectName("notice")
        self.description.setWordWrap(True)
        self.description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.description.hide()
        self.layout.addWidget(self.description)
        self.card_gap = self.layout.count()
        self.layout.addSpacing(20)

        self.card = Card()
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(20, 18, 20, 18)
        card_layout.setSpacing(0)
        row = QHBoxLayout()
        row.setSpacing(6)
        caption = QLabel("TRANSCRIPT")
        caption.setObjectName("eyebrow")
        row.addWidget(caption)
        row.addStretch()
        self.status_dot = QLabel()
        self.status_dot.setObjectName("statusDot")
        self.status_dot.setFixedSize(7, 7)
        row.addWidget(self.status_dot)
        self.result_status = QLabel(self.final_status)
        self.result_status.setObjectName("resultStatus")
        row.addWidget(self.result_status)
        card_layout.addLayout(row)
        card_layout.addSpacing(14)
        self.text = QTextEdit()
        self.text.setObjectName("transcript")
        self.text.setAcceptRichText(False)
        self.text.setFrameShape(QFrame.Shape.NoFrame)
        self.text.setMinimumHeight(44)
        self.text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.text.document().setDocumentMargin(0)
        self.text.setAutoFillBackground(False)
        self.text.viewport().setAutoFillBackground(False)
        self.text.setAccessibleName("Transcription")
        self.empty_hint = QLabel("Press Record and speak naturally.\nYour words will appear here.", self.text.viewport())
        self.empty_hint.setObjectName("emptyHint")
        self.empty_hint.setWordWrap(True)
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.empty_hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.text.viewport().installEventFilter(self)
        card_layout.addWidget(self.text, 1)
        card_layout.addSpacing(12)
        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFixedHeight(1)
        card_layout.addWidget(divider)
        card_layout.addSpacing(12)
        footer = QHBoxLayout()
        self.clear = QPushButton("Clear")
        self.clear.setObjectName("clear")
        self.clear.setFixedSize(98, 36)
        self.clear.setIconSize(QSize(18, 18))
        self.clear.clicked.connect(self.clear_text)
        footer.addWidget(self.clear)
        footer.addStretch()
        self.copy = QPushButton("Copy text")
        self.copy.setObjectName("copy")
        self.copy.setFixedSize(120, 36)
        self.copy.setIconSize(QSize(18, 18))
        self.copy.clicked.connect(self.copy_text)
        footer.addWidget(self.copy)
        card_layout.addLayout(footer)
        self.shadow = QGraphicsDropShadowEffect(self.card)
        self.shadow.setBlurRadius(22)
        self.shadow.setOffset(0, 5)
        self.card.setGraphicsEffect(self.shadow)
        self.layout.addWidget(self.card, 1)
        self.copy_timer = QTimer(self)
        self.copy_timer.setSingleShot(True)
        self.copy_timer.timeout.connect(self._reset_copy)
        self.controller = ThemeController(self, override=theme)
        self.controller.changed.connect(self.apply_theme)
        self.apply_theme(self.controller.theme)
        self.set_state(State.LOADING)
        self.text.textChanged.connect(self._text_edited)
        # Start with keyboard focus on the primary action, without displaying a
        # focus ring until keyboard navigation actually requests one.
        self.record.setFocus()

    def apply_theme(self, theme):
        scrollbar = self.text.verticalScrollBar()
        position, cursor = scrollbar.value(), self.text.textCursor()
        self.theme = theme
        QApplication.instance().setPalette(palette_for(theme))
        for painted in (self.root, self.card, self.record, self.meter):
            painted.theme = theme
            painted.update()
        self.shadow.setColor(QColor(0, 0, 0, 65) if theme.dark else QColor(36, 28, 80, 15))
        self.setStyleSheet(f"""
            QWidget {{ font-family: 'Segoe UI'; font-size: 12px; color: {theme.ink}; }}
            QLabel {{ background: transparent; }}
            QLabel#subtitle {{ color: {theme.muted}; font-size: 14px; }}
            QLabel#badge {{ color: {theme.accent_text}; background: {theme.badge};
                           border: 1px solid {theme.badge}; border-radius: 12px;
                           padding: 3px 10px; font-size: 11px; }}
            QLabel#caption {{ color: {theme.muted}; font-size: 11px; }}
            QLabel#notice {{ color: {theme.muted}; font-size: 11px; padding-top: 4px; }}
            QLabel#eyebrow {{ color: {theme.muted}; font-size: 10px; letter-spacing: 1.4px; }}
            QLabel#resultStatus {{ color: {theme.muted}; font-size: 11px; }}
            QLabel#statusDot {{ background: {theme.disabled}; border-radius: 3px; }}
            QLabel#emptyHint {{ color: {theme.muted}; background: transparent; font-size: 15px; }}
            QTextEdit#transcript {{ background: transparent; color: {theme.ink};
                                   font-size: 16px; border: none; padding: 0; }}
            QFrame#divider {{ background: {theme.border}; }}
            QPushButton#clear, QPushButton#copy {{ border: 1px solid {theme.border};
                border-radius: 18px; padding: 4px 9px; font-size: 12px; color: {theme.ink}; }}
            QPushButton#clear {{ background: transparent; }}
            QPushButton#copy {{ background: {theme.action}; color: {theme.accent_text}; border-color: {theme.action}; }}
            QPushButton#clear:hover, QPushButton#copy:hover {{ background: {theme.badge}; border-color: {theme.accent_text}; }}
            QPushButton#clear:pressed, QPushButton#copy:pressed {{ background: {theme.selection}; }}
            QPushButton#clear:focus, QPushButton#copy:focus {{ border: 2px solid {theme.accent_text}; }}
            QPushButton#clear:disabled, QPushButton#copy:disabled {{ color: {theme.disabled}; border-color: {theme.border}; }}
            QPushButton#copy:disabled {{ background: {'#252a37' if theme.dark else '#f2f3f7'}; }}
            QScrollBar:vertical {{ background: transparent; width: 6px; margin: 0; }}
            QScrollBar::handle:vertical {{ background: {theme.border}; border-radius: 3px; min-height: 24px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
            QMenu {{ background: {theme.card[0]}; color: {theme.ink}; border: 1px solid {theme.border}; }}
            QMenu::item:selected {{ background: {theme.selection}; }}
            QToolTip {{ background: {theme.card[0]}; color: {theme.ink}; border: 1px solid {theme.border}; }}
        """)
        self.text.setTextCursor(cursor)
        scrollbar.setValue(position)
        self._status()
        self._actions()
        self.header.position()
        self._arrange()
        style_native_frame(self, theme)

    def eventFilter(self, watched, event):
        if hasattr(self, "hero") and watched is self.hero and event.type() == QEvent.Type.Resize:
            self._position_controls()
        if hasattr(self, "text") and watched is self.text.viewport() and event.type() == QEvent.Type.Resize:
            self.empty_hint.setGeometry(0, 2, watched.width(), max(44, watched.height() - 2))
        return super().eventFilter(watched, event)

    def _arrange(self):
        if not hasattr(self, "theme"):
            return
        compact = self.width() < 500
        notice = not self.description.isHidden()
        self.layout.setContentsMargins(24 if compact else 28, 16 if compact else 24,
                                       24 if compact else 28, 16 if compact else 20)
        self.header.arrange(compact)
        self.record.set_compact(compact or notice)
        if compact and notice:
            self.record.diameter = 112
            self.record.setFixedSize(152, 152)
        self.layout.itemAt(self.hero_gap).spacerItem().changeSize(0, 4 if compact else 8)
        self.layout.itemAt(self.card_gap).spacerItem().changeSize(0, 8 if compact else 14)
        self.meter.setFixedHeight(40 if compact else 56)
        # Let the larger waveform overlap the fading edge of the halo, rather
        # than taking space away from readable transcript lines.
        self.hero.setFixedHeight(self.record.height() + self.meter.height() - 20)
        self._position_controls()
        self.layout.invalidate()

    def _position_controls(self):
        if not hasattr(self, "meter"):
            return
        self.record.move((self.hero.width() - self.record.width()) // 2, 0)
        self.meter.setGeometry(0, self.record.height() - 20, self.hero.width(), self.meter.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._arrange()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and hasattr(self, "meter"):
            self.record.sync_timer()
            self.meter.sync_timer()

    def showEvent(self, event):
        super().showEvent(event)
        style_native_frame(self, self.theme)

    @Slot(object)
    def handle(self, event: Event):
        if event.kind == "state":
            self.set_state(event.value)
        elif event.kind == "text":
            self.set_session_text(event.value)
        elif event.kind == "backend":
            device, notice = event.value
            self.backend = f"{'CUDA' if device == 'cuda' else 'CPU'} • TURBO"
            self.badge.setText(self.backend)
            self.backend_notice = notice
            self.header.position()
            self._notice()
        elif event.kind == "level":
            self.meter.level, self.seconds = event.value
            self._status()
        elif event.kind == "error":
            self.error_message = str(event.value)
            self._notice()
        elif event.kind == "final":
            self.set_session_text(event.value)
            self.final_status = "Complete" if event.value else "No speech detected"
            self._status()

    def set_state(self, state):
        if state == State.STARTING and self.state != State.STARTING:
            # Whisper revisions replace only this recording's provisional tail.
            # Everything visible before Record stays immutable until Clear.
            self._recording_prefix = self.text.toPlainText().rstrip()
            self.text.verticalScrollBar().setValue(self.text.verticalScrollBar().maximum())
        self.state = state
        editing_locked = state in (State.STARTING, State.RECORDING, State.FINALIZING, State.CLOSED)
        self.text.setReadOnly(editing_locked)
        self.text.setToolTip("Finish recording to edit the transcript." if editing_locked else
                             "Edit your transcript here. Your changes are included when you copy.")
        active = state in (State.STARTING, State.RECORDING)
        self.record.setText("Finish" if active else "Finishing…" if state == State.FINALIZING else
                            "Loading…" if state == State.LOADING else "Record")
        self.record.setEnabled(state in (State.READY, State.STARTING, State.RECORDING) or
                               bool(state == State.ERROR and self.service and self.service.model_ready))
        self.record.set_mode(state)
        self.meter.active = state == State.RECORDING
        self.meter.sync_timer()
        if state == State.STARTING:
            self.error_message = ""
            self.final_status = "Ready for your voice"
            self.seconds = 0
        self._status()
        self._notice()
        self._actions()

    def _status(self):
        elapsed = f"{int(self.seconds) // 60:02d}:{int(self.seconds) % 60:02d}"
        statuses = {State.LOADING: "Getting ready…", State.STARTING: "Opening microphone…",
                    State.RECORDING: f"Live · {elapsed}", State.FINALIZING: "Finishing…",
                    State.ERROR: "Please try again", State.CLOSED: "Closing…"}
        self.result_status.setText(statuses.get(self.state, self.final_status))
        color = self.theme.rose[1] if self.state == State.RECORDING else (
            "#78b5a0" if self.final_status == "Complete" and self.state == State.READY else self.theme.disabled)
        self.status_dot.setStyleSheet(f"background: {color}; border-radius: 3px;")

    def _notice(self):
        loading = "Loading Whisper Turbo. The model stays warm." if self.state == State.LOADING else ""
        message = self.error_message if self.state == State.ERROR else self.backend_notice or loading
        self.description.setText(message)
        self.description.setVisible(bool(message))
        self.description.setAccessibleName(message)
        self._arrange()

    def set_text(self, text):
        scrollbar = self.text.verticalScrollBar()
        at_bottom = scrollbar.value() >= scrollbar.maximum() - 4
        old_position = scrollbar.value()
        self._setting_text = True
        try:
            self.text.setPlainText(text)
            cursor = QTextCursor(self.text.document())
            cursor.select(QTextCursor.SelectionType.Document)
            block = QTextBlockFormat()
            block.setLineHeight(145, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
            cursor.mergeBlockFormat(block)
            # Model rendering is not a user undo step.
            self.text.document().clearUndoRedoStacks()
        finally:
            self._setting_text = False
        self.empty_hint.setVisible(not bool(text))
        scrollbar.setValue(scrollbar.maximum() if at_bottom else old_position)
        self._reset_copy()
        self._actions()

    def _text_edited(self):
        if self._setting_text:
            return
        populated = bool(self.text.toPlainText())
        self.empty_hint.setVisible(not populated)
        self.final_status = "Edited" if populated else "Ready for your voice"
        self._reset_copy()
        self._status()

    def set_session_text(self, text):
        combined = "\n\n".join(part for part in (self._recording_prefix, text.strip()) if part)
        if combined != self.text.toPlainText():
            self.set_text(combined)

    def _actions(self):
        populated = bool(self.text.toPlainText())
        self.copy.setEnabled(populated)
        self.clear.setEnabled(populated and self.state in (State.READY, State.ERROR))
        self.clear.setIcon(symbol_icon("clear", self.theme.ink if self.clear.isEnabled() else self.theme.disabled))
        self.copy.setIcon(symbol_icon("check" if self._copied else "copy",
                                      self.theme.accent_text if self.copy.isEnabled() else self.theme.disabled))

    def toggle(self):
        if self.service:
            if self.state in (State.STARTING, State.RECORDING):
                self.service.stop()
            else:
                self.service.start()

    def copy_text(self):
        QApplication.clipboard().setText(self.text.toPlainText())
        self._copied = True
        self.copy.setText("Copied")
        self._actions()
        self.copy_timer.start(1800)

    def _reset_copy(self):
        self.copy_timer.stop()
        self._copied = False
        self.copy.setText("Copy text")
        self._actions()

    def clear_text(self):
        self._recording_prefix = ""
        self.set_text("")
        self.final_status = "Ready for your voice"
        self._status()

    def closeEvent(self, event):
        self.record.timer.stop()
        self.meter.timer.stop()
        self.record.animation.stop()
        self.record.press_animation.stop()
        if self.service:
            self.service.close()
        event.accept()
