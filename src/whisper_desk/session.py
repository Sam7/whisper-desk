"""Two background owners: audio lifecycle and serial resident-model inference."""
from dataclasses import dataclass, field
import logging
from queue import Queue, Empty
from threading import Event as Flag, Lock, Thread
from time import perf_counter
import sys

from .audio import AudioBuffer, Microphone
from .config import Config
from .engine import WhisperEngine
from .installation import SetupRepairRequired
from .models import Event, State
from .transcript import Transcript

log = logging.getLogger(__name__)


@dataclass
class Recording:
    buffer: AudioBuffer
    transcript: Transcript
    clicked: float
    captured: Flag = field(default_factory=Flag)
    stopped: Flag = field(default_factory=Flag)
    stop_clicked: float | None = None
    reported_capture: bool = False


class SessionService:
    def __init__(self, emit, config=None, engine=None, recorder=None):
        self.emit = emit
        self.config = config or Config()
        self.engine = engine or WhisperEngine(self.config)
        self.recorder = recorder or Microphone()
        self.state = State.LOADING
        self.recording = None
        self._lock = Lock()
        self._quit = Flag()
        self._wake = Flag()
        self._commands = Queue()
        self._threads = []
        self.model_ready = False

    def _state(self, state):
        self.state = state
        self.emit(Event("state", state))

    def launch(self):
        self._commands.put(("prepare", None))
        for target, name in ((self._capture_loop, "audio"), (self._inference_loop, "whisper")):
            thread = Thread(target=target, name=name, daemon=True)
            self._threads.append(thread)
            thread.start()

    def start(self):
        with self._lock:
            if self.state not in (State.READY, State.ERROR) or not self.model_ready:
                return False
            rec = Recording(AudioBuffer(self.config.sample_rate, self.config.max_backlog),
                            Transcript(self.config), perf_counter())
            self.recording = rec
            self._state(State.STARTING)
            self.emit(Event("text", ""))
            self._commands.put(("start", rec))
            return True

    def stop(self):
        with self._lock:
            if self.state not in (State.STARTING, State.RECORDING):
                return False
            rec = self.recording
            rec.stop_clicked = perf_counter()
            self._state(State.FINALIZING)
            self._commands.put(("stop", rec))
            return True

    def close(self):
        with self._lock:
            if self._quit.is_set():
                return
            self._quit.set()
            self._state(State.CLOSED)
            self._commands.put(("close", self.recording))
            self._wake.set()

    def join(self, timeout=2):
        for thread in self._threads:
            thread.join(timeout)

    def _fail(self, message, rec=None):
        log.error(message, exc_info=sys.exc_info()[0] is not None)
        with self._lock:
            if self._quit.is_set() or (rec is not None and rec is not self.recording):
                return
            self.recording = None
            self._commands.put(("reset", rec))
            self.emit(Event("error", message))
            self._state(State.ERROR)

    def _capture_loop(self):
        while True:
            command, rec = self._commands.get()
            if command == "prepare":
                try:
                    if hasattr(self.recorder, "prepare"):
                        self.recorder.prepare()
                except Exception:
                    log.exception("Microphone preparation failed; will retry on Record")
            elif command == "start":
                if self._quit.is_set():
                    continue
                try:
                    self.recorder.start(rec.buffer)
                    rec.captured.set()
                    with self._lock:
                        if self.state == State.STARTING and self.recording is rec:
                            self._state(State.RECORDING)
                    self._wake.set()
                except Exception:
                    self._fail("Microphone unavailable. Check Windows microphone access and your input device.", rec)
            else:
                try:
                    if command in ("close", "reset") and hasattr(self.recorder, "close"):
                        self.recorder.close()
                    else:
                        self.recorder.stop()
                except Exception:
                    log.exception("Microphone close failed")
                if rec:
                    rec.stopped.set()
                self._wake.set()
                if command == "close":
                    return

    def _inference_loop(self):
        try:
            device, notice = self.engine.load()
            with self._lock:
                if self._quit.is_set():
                    return
                self.model_ready = True
                self.emit(Event("backend", (device, notice)))
                self._state(State.READY)
        except Exception as exc:
            self._fail(str(exc) if isinstance(exc, SetupRepairRequired) else
                       "Could not load Whisper Turbo. Check your connection for the first model download, then restart.")
            return
        while not self._quit.is_set():
            rec = self.recording
            if rec is None or not rec.captured.is_set():
                self._wake.wait(0.03)
                self._wake.clear()
                continue
            try:
                self._process(rec)
            except Exception:
                self._fail("Transcription failed. Your visible text is preserved; please try recording again.", rec)

    def _process(self, rec):
        last_end = 0.0
        first_text = True
        language = self.config.language
        last_word_end = None
        while not self._quit.wait(0.025) and self.recording is rec:
            buffer = rec.buffer
            if buffer.error:
                self._fail(buffer.error, rec)
                return
            if buffer.first_capture is not None and not rec.reported_capture:
                log.info("Recording started: %.0f ms after click", (buffer.first_capture - rec.clicked) * 1000)
                rec.reported_capture = True
            end = buffer.end
            final = rec.stopped.is_set()
            self.emit(Event("level", (buffer.level, end)))
            if not final and (end < self.config.first_window or end - last_end < self.config.interval):
                continue
            start = rec.transcript.start
            window_end = min(end, start + self.config.max_window)
            is_last = final and window_end >= end
            audio = buffer.snapshot(start, window_end)
            began = perf_counter()
            can_reuse = (is_last and last_word_end is not None and
                         end - last_word_end >= 0.35 and 0 <= end - last_end <= 1.0 and
                         hasattr(self.engine, "has_speech") and
                         not self.engine.has_speech(buffer.snapshot(max(0, last_end - 0.25), end)))
            if can_reuse:
                text = rec.transcript.finish(end)
                log.info("Final result reused: only silence arrived after the last decode")
            elif len(audio) >= 1600:
                words, detected = self.engine.transcribe(audio, final=is_last, language=language)
                if words:
                    language = detected
                    last_word_end = start + words[-1].end
                text = rec.transcript.update(words, start, window_end, final=is_last)
            else:
                text = rec.transcript.text
            if self._quit.is_set() or self.recording is not rec:
                return
            self.emit(Event("text", text))
            if text and first_text:
                log.info("First transcript: %.0f ms after click", (perf_counter() - rec.clicked) * 1000)
                first_text = False
            log.info("%s inference: %.0f ms; audio %.2f–%.2f s; backlog %.2f s",
                     "Final" if is_last else "Incremental", (perf_counter() - began) * 1000,
                     start, window_end, max(0, buffer.end - window_end))
            last_end = window_end
            buffer.prune(rec.transcript.start)
            if is_last:
                log.info("Stop → final transcript: %.0f ms", (perf_counter() - (rec.stop_clicked or began)) * 1000)
                with self._lock:
                    if self.recording is rec and not self._quit.is_set():
                        self.recording = None
                        self.emit(Event("final", text))
                        self._state(State.READY)
                return
