from threading import Event as Flag
from time import monotonic, sleep

import numpy as np
import pytest

from whisper_desk.config import Config
from whisper_desk.models import State, Word
from whisper_desk.session import SessionService
from whisper_desk.installation import SetupRepairRequired


def test_installed_model_failure_shows_repair_instruction():
    class MissingModel:
        def load(self):
            raise SetupRepairRequired("Run the installer again to repair the model.")
    events = []
    service = SessionService(events.append, engine=MissingModel(), recorder=FakeRecorder())
    try:
        service.launch()
        wait(lambda: service.state == State.ERROR)
        assert not service.model_ready
        assert [e.value for e in events if e.kind == "error"] == ["Run the installer again to repair the model."]
    finally:
        service.close()
        service.join()


def wait(predicate, timeout=3):
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        if predicate():
            return
        sleep(0.005)
    raise AssertionError("Timed out waiting for expected state")


class FakeEngine:
    def __init__(self):
        self.loads = 0
        self.calls = []
        self.failure = False
        self.block = None

    def load(self):
        self.loads += 1
        return "cuda", ""

    def transcribe(self, audio, **kwargs):
        self.calls.append(kwargs)
        if self.block:
            self.block.wait(2)
        if self.failure:
            raise RuntimeError("inference failed")
        return [Word(0, 0.2, " Hello"), Word(0.2, 0.4, " world.")], "en"


class FakeRecorder:
    def __init__(self):
        self.buffer = None
        self.stops = 0
        self.failure = False

    def start(self, buffer):
        if self.failure:
            raise RuntimeError("no mic")
        self.buffer = buffer

    def stop(self):
        self.stops += 1

    def feed(self, seconds=0.6):
        self.buffer.append(np.ones(round(seconds * 16000), np.float32) * 0.02)


@pytest.fixture
def service():
    events, engine, recorder = [], FakeEngine(), FakeRecorder()
    config = Config(first_window=0.4, interval=0.2)
    service = SessionService(events.append, config, engine, recorder)
    service.launch()
    wait(lambda: service.state == State.READY)
    yield service, engine, recorder, events
    service.close()
    if engine.block:
        engine.block.set()
    service.join()
    assert not any(t.is_alive() for t in service._threads)


def test_live_then_final_and_repeated_sessions_keep_model(service):
    s, e, r, events = service
    for _ in range(2):
        assert s.start()
        wait(lambda: s.state == State.RECORDING)
        r.feed()
        wait(lambda: any(x.kind == "text" and x.value for x in events))
        assert s.state == State.RECORDING
        assert s.stop()
        wait(lambda: s.state == State.READY)
        assert [x.value for x in events if x.kind == "final"][-1] == "Hello world."
        events.clear()
    assert e.loads == 1
    assert any(not call["final"] for call in e.calls)
    assert any(call["final"] for call in e.calls)


def test_real_event_bridge_keeps_two_recordings_and_clear(service, qtbot):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from whisper_desk.ui import Bridge, MainWindow

    s, engine, recorder, events = service
    bridge = Bridge(QApplication.instance())
    s.emit = bridge.event.emit
    window = MainWindow(s, theme="dark")
    bridge.event.connect(window.handle)
    qtbot.addWidget(window)
    window.show()
    window.set_state(State.READY)
    for count in (1, 2):
        qtbot.mouseClick(window.record, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(lambda: window.state == State.RECORDING)
        recorder.feed()
        qtbot.waitUntil(lambda: window.text.toPlainText().count("Hello world.") == count)
        qtbot.mouseClick(window.record, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(lambda: window.state == State.READY)
        assert window.text.toPlainText() == "\n\n".join(["Hello world."] * count)
    window.copy.click()
    assert QApplication.clipboard().text() == "Hello world.\n\nHello world."
    assert engine.loads == 1
    window.clear.click()
    assert window.text.toPlainText() == ""


def test_rapid_start_stop_no_duplicate_session(service):
    s, e, r, events = service
    assert s.start()
    assert not s.start()
    assert s.stop()
    assert not s.stop()
    wait(lambda: s.state == State.READY)
    assert len([x for x in events if x.kind == "final"]) == 1


def test_microphone_error_can_retry(service):
    s, e, r, events = service
    r.failure = True
    assert s.start()
    wait(lambda: s.state == State.ERROR)
    assert any(x.kind == "error" and "Microphone" in x.value for x in events)
    r.failure = False
    assert s.start()
    wait(lambda: s.state == State.RECORDING)


def test_inference_failure_stops_capture_and_can_retry(service):
    s, e, r, events = service
    e.failure = True
    s.start()
    wait(lambda: s.state == State.RECORDING)
    r.feed()
    wait(lambda: s.state == State.ERROR)
    wait(lambda: r.stops > 0)
    assert not any(x.kind == "final" for x in events)
    e.failure = False
    assert s.start()
    wait(lambda: s.state == State.RECORDING)


def test_stop_does_not_wait_for_inference(service):
    s, e, r, events = service
    e.block = Flag()
    s.start()
    wait(lambda: s.state == State.RECORDING)
    r.feed()
    wait(lambda: bool(e.calls))
    began = monotonic()
    s.stop()
    assert monotonic() - began < 0.1
    wait(lambda: r.stops > 0)
    assert s.state == State.FINALIZING
    e.block.set()
    wait(lambda: s.state == State.READY)


def test_close_during_inference_suppresses_late_results(service):
    s, e, r, events = service
    e.block = Flag()
    s.start()
    wait(lambda: s.state == State.RECORDING)
    r.feed()
    wait(lambda: bool(e.calls))
    s.close()
    e.block.set()
    s.join()
    assert s.state == State.CLOSED
    assert not any(x.kind == "final" for x in events)


def test_audio_device_disappearance(service):
    s, e, r, events = service
    s.start()
    wait(lambda: s.state == State.RECORDING)
    r.buffer.error = "The microphone disconnected."
    wait(lambda: s.state == State.ERROR)
    wait(lambda: r.stops > 0)


def test_loading_failure_is_reported():
    class Broken(FakeEngine):
        def load(self):
            raise RuntimeError("download error")
    events = []
    s = SessionService(events.append, engine=Broken(), recorder=FakeRecorder())
    s.launch()
    wait(lambda: s.state == State.ERROR)
    assert not s.start()
    assert any(x.kind == "error" for x in events)
    s.close()
    s.join()


def test_long_backlog_is_drained_in_overlapping_windows_without_lost_words():
    class CountingEngine(FakeEngine):
        def transcribe(self, audio, **kwargs):
            self.calls.append((len(audio), kwargs))
            offset = float(audio[0])
            end = offset + len(audio) / 16000
            words = [Word(i + 0.1 - offset, i + 0.5 - offset, f" word{i}.")
                     for i in range(60) if i + 0.1 >= offset and i + 0.5 <= end]
            return words, "en"

    events, engine, recorder = [], CountingEngine(), FakeRecorder()
    s = SessionService(events.append, Config(max_window=12), engine, recorder)
    s.launch()
    wait(lambda: s.state == State.READY)
    s.start()
    wait(lambda: s.state == State.RECORDING)
    recorder.buffer.append(np.arange(60 * 16000, dtype=np.float32) / 16000)
    s.stop()
    wait(lambda: s.state == State.READY)
    expected = " ".join(f"word{i}." for i in range(60))
    assert [e.value for e in events if e.kind == "final"] == [expected]
    assert len(engine.calls) > 1
    assert max(n for n, _ in engine.calls) <= 12 * 16000
    assert len(recorder.buffer.snapshot()) < 12 * 16000
    s.close()
    s.join()


def test_stop_reuses_complete_live_decode_when_only_silence_arrives():
    class SilentTailEngine(FakeEngine):
        def has_speech(self, audio):
            return False

    events, engine, recorder = [], SilentTailEngine(), FakeRecorder()
    s = SessionService(events.append, Config(first_window=0.4, interval=1.0), engine, recorder)
    s.launch()
    wait(lambda: s.state == State.READY)
    s.start()
    wait(lambda: s.state == State.RECORDING)
    recorder.feed(1.0)
    wait(lambda: any(e.kind == "text" and e.value for e in events))
    recorder.feed(0.2)
    s.stop()
    wait(lambda: s.state == State.READY)
    assert len(engine.calls) == 1
    assert [e.value for e in events if e.kind == "final"] == ["Hello world."]
    s.close()
    s.join()
