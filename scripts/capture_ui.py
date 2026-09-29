"""Deterministic native Qt rendering. No microphone/model or OS theme changes."""
import argparse
import json
import os
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from whisper_desk.models import Event, State
from whisper_desk.ui import MainWindow

SAMPLE = "Let’s keep this simple. A little space to think out loud, and turn those thoughts into words."
LONG = ("Today I want to make room for focused work. I’ll start with the most important task, take a short break, and come back with a fresh perspective. " * 12).strip()
CASES = [
    ("empty", State.READY, "", 540, 770),
    ("starting", State.STARTING, "", 540, 770),
    ("recording", State.RECORDING, "Let’s keep this simple. A little space to think", 540, 770),
    ("silence", State.RECORDING, "", 540, 770),
    ("result", State.READY, SAMPLE, 540, 770),
    ("short", State.READY, "A thought worth keeping.", 540, 770),
    ("long-narrow", State.READY, LONG, 440, 560),
    ("empty-narrow", State.READY, "", 440, 560),
    ("loading", State.LOADING, "", 540, 770),
    ("finalizing", State.FINALIZING, SAMPLE, 540, 770),
    ("no-speech", State.READY, "", 540, 770),
    ("error", State.ERROR, SAMPLE, 440, 560),
    ("cpu", State.READY, SAMPLE, 440, 560),
    ("hover", State.READY, "", 540, 770),
    ("pressed", State.READY, "", 540, 770),
    ("focus", State.READY, "", 540, 770),
    ("copied", State.READY, SAMPLE, 540, 770),
    ("append-recording", State.RECORDING, "A second thought is taking shape.", 540, 770),
    ("history-result", State.READY, SAMPLE + "\n\nA second thought worth keeping.", 540, 770),
    ("edited", State.READY, SAMPLE, 540, 770),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="artifacts/ui-redesign")
    parser.add_argument("--theme", choices=["light", "dark", "both"], default="both")
    args = parser.parse_args()
    output = Path(args.output)
    app = QApplication([])
    if app.platformName() == "offscreen":
        # The headless Qt platform does not discover Windows system fonts.
        fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        for filename in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf"):
            if (fonts / filename).exists():
                QFontDatabase.addApplicationFont(str(fonts / filename))
    app.setStyle("Fusion")
    themes = ["light", "dark"] if args.theme == "both" else [args.theme]
    cases = iter((theme, case) for theme in themes for case in CASES)
    current = None
    reports = []

    def next_case():
        nonlocal current
        if current:
            current.close()
            current.deleteLater()
        try:
            theme, (name, state, text, width, height) = next(cases)
        except StopIteration:
            (output / "geometry.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
            app.quit()
            return
        window = MainWindow(theme=theme)
        window.service = SimpleNamespace(model_ready=True, close=lambda: None)
        current = window
        window.record.preview_phase = 0.7
        window.meter.preview_phase = 0.7
        window.resize(width, height)
        window.handle(Event("backend", ("cuda", "")))
        window.set_text(text)
        window.set_state(state)
        window.handle(Event("level", (0 if name == "silence" else 0.08, 8)))
        if state == State.READY and text:
            window.final_status = "Complete"
            window._status()
        if name == "no-speech":
            window.handle(Event("final", ""))
        if name == "error":
            window.handle(Event("error", "Microphone unavailable. Check Windows microphone access and your input device."))
        if name == "cpu":
            window.handle(Event("backend", ("cpu", "CUDA could not start. Using CPU. See the log for details.")))
        window.record.preview_hover = name == "hover"
        window.record.preview_focus = name == "focus"
        window.record.setDown(name == "pressed")
        if name == "copied":
            window.copy_text()
        if name == "edited":
            window.text.selectAll()
            window.text.insertPlainText("A corrected thought. You can edit, paste and refine your words here.")
            window.text.setFocus()
        if name == "append-recording":
            window.set_text(SAMPLE)
            window.set_state(State.READY)
            window.set_state(State.STARTING)
            window.set_state(State.RECORDING)
            window.handle(Event("text", text))
            window.handle(Event("level", (0.08, 8)))
        window.show()
        scrollbar = window.text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum() if name in ("append-recording", "history-result") else 0)
        QTimer.singleShot(100, lambda: save(window, theme, name))

    def save(window, theme, name):
        folder = output / theme
        folder.mkdir(parents=True, exist_ok=True)
        window.grab().save(str(folder / f"{name}.png"))
        reports.append({"theme": theme, "state": name,
                        "size": [window.width(), window.height()], "dpr": window.devicePixelRatioF(),
                        "card_height": window.card.height(), "text_height": window.text.viewport().height(),
                        "hint_height": window.empty_hint.sizeHint().height(),
                        "notice": window.description.text()})
        QTimer.singleShot(0, next_case)

    # Each case gets a clean window; closing it must not exit between cases.
    app.setQuitOnLastWindowClosed(False)
    QTimer.singleShot(0, next_case)
    app.exec()


if __name__ == "__main__":
    main()
