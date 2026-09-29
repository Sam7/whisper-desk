"""Exercise real Qt controls and CUDA inference with repeatable speech or a microphone."""
import argparse
import json
import logging
from pathlib import Path
from threading import Event as Flag, Thread
from time import perf_counter

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from whisper_desk.audio import Microphone
from whisper_desk.config import Config
from whisper_desk.models import State
from whisper_desk.session import SessionService
from whisper_desk.ui import Bridge, MainWindow


class SampleRecorder:
    def __init__(self, samples):
        self.samples = samples
        self.done = Flag()
        self.cancel = Flag()
        self.thread = None

    def start(self, buffer):
        self.done.clear()
        self.cancel.clear()

        def feed():
            began = perf_counter()
            for i in range(0, len(self.samples), 320):
                if self.cancel.is_set():
                    break
                buffer.append(self.samples[i:i + 320])
                if self.cancel.wait(max(0, began + (i + 320) / 16000 - perf_counter())):
                    break
            self.done.set()

        self.thread = Thread(target=feed, daemon=True)
        self.thread.start()

    def stop(self):
        self.cancel.set()
        if self.thread:
            self.thread.join(1)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--microphone", action="store_true", help="Capture real default WASAPI input for 6 seconds")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--output", default="artifacts/exercise")
    parser.add_argument("--audio", default="tests/data/jfk.flac")
    parser.add_argument("--theme", choices=["system", "light", "dark"], default="system")
    parser.add_argument("--sessions", type=int, default=1, help="Record again without clearing between sessions")
    args = parser.parse_args(argv)
    if args.sessions < 1:
        parser.error("--sessions must be at least 1")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(output / "timings.log", encoding="utf-8")])
    if args.microphone:
        recorder = Microphone()
    else:
        from faster_whisper.audio import decode_audio
        sample = decode_audio(args.audio)
        recorder = SampleRecorder(np.tile(sample, args.repeat))
    app = QApplication([])
    app.setStyle("Fusion")
    bridge = Bridge()
    service = SessionService(bridge.event.emit, Config(), recorder=recorder)
    window = MainWindow(service, theme=None if args.theme == "system" else args.theme)
    bridge.event.connect(window.handle)
    history, heartbeats = [], []
    started = None
    stopped = None
    phase = "loading"
    failure = []
    first_text = None
    completed = False
    session_index = 1
    session_reports = []
    previous_text = ""

    def handle(event):
        nonlocal first_text
        if event.kind != "level":
            history.append({"time": perf_counter(), "kind": event.kind, "value": event.value})
        if event.kind == "text" and event.value and started and first_text is None:
            first_text = perf_counter() - started
        if event.kind == "error":
            failure.append(event.value)

    bridge.event.connect(handle)
    window.show()
    service.launch()
    deadline = perf_counter() + 120 + args.repeat * args.sessions * 12

    def tick():
        nonlocal phase, started, stopped, completed, session_index, first_text, previous_text
        now = perf_counter()
        heartbeats.append(now)
        if failure or now > deadline:
            if now > deadline:
                failure.append("Timed out")
            finish()
            return
        if phase == "loading" and window.state == State.READY:
            window.grab().save(str(output / "empty.png"))
            started = now
            window.record.click()
            phase = "recording"
        elif phase == "recording":
            if now - started > 5:
                window.grab().save(str(output / "recording.png"))
                phase = "wait-stop"
        elif phase == "wait-stop" and ((args.microphone and now - started >= 6) or
                                        (not args.microphone and recorder.done.is_set())):
            stopped = now
            window.record.click()
            phase = "finalizing"
        elif phase == "finalizing" and window.state == State.READY:
            text = window.text.toPlainText()
            window.grab().save(str(output / "result.png"))
            window.grab().save(str(output / f"result-{session_index}.png"))
            if previous_text and not text.startswith(previous_text + "\n\n"):
                failure.append("Earlier recording was overwritten")
            if text:
                window.copy.click()
            if text and QApplication.clipboard().text() != text:
                failure.append("Clipboard mismatch")
            if not args.microphone:
                normalized = text.lower()
                for phrase in ("my fellow americans", "ask not what your country can do for you", "ask what you can do for your country"):
                    expected = args.repeat * session_index
                    if normalized.count(phrase) != expected:
                        failure.append(f"Expected {expected} copies of known speech: {phrase}")
                if first_text is None or first_text >= stopped - started:
                    failure.append("No live transcript before Stop")
            report = {"backend": window.backend, "text": text,
                      "first_text_ms": round(first_text * 1000) if first_text is not None else None,
                      "stop_to_final_ms": round((now - stopped) * 1000),
                      "max_gui_heartbeat_gap_ms": round(max(np.diff(heartbeats)) * 1000),
                      "errors": failure, "events": history}
            session_reports.append({key: value for key, value in report.items() if key not in ("events", "errors")})
            report["sessions"] = session_reports
            (output / "report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
            print(json.dumps({k: v for k, v in report.items() if k != "events"}, indent=2))
            if not failure and session_index < args.sessions:
                previous_text = text
                session_index += 1
                first_text = None
                started = now
                window.record.click()
                if window.text.toPlainText() != previous_text:
                    failure.append("Record cleared earlier text")
                phase = "recording"
                return
            window.clear.click()
            if window.text.toPlainText():
                failure.append("Clear failed")
            completed = True
            finish()

    def finish():
        timer.stop()
        window.close()
        app.quit()

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(15)
    app.exec()
    service.close()
    service.join()
    if not completed and not failure:
        failure.append("The test window closed before the exercise completed; rerun it")
    if failure:
        raise SystemExit("; ".join(failure))


if __name__ == "__main__":
    main()
