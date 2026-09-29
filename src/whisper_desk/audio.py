"""Audio boundaries, with no dependency on Qt or Whisper."""
from collections import deque
from threading import Lock
from time import perf_counter
import logging

import numpy as np


class AudioBuffer:
    """Absolute sample positions survive pruning. Callback work is O(block size)."""

    def __init__(self, rate=16000, max_seconds=120):
        self.rate = rate
        self.limit = int(rate * max_seconds)
        self._blocks = deque()
        self._end = 0
        self._lock = Lock()
        self.level = 0.0
        self.first_capture = None
        self.error = None

    @property
    def end(self):
        with self._lock:
            return self._end / self.rate

    def append(self, samples):
        block = np.asarray(samples, dtype=np.float32).reshape(-1).copy()
        with self._lock:
            if self.first_capture is None:
                self.first_capture = perf_counter()
            first = self._blocks[0][0] if self._blocks else self._end
            if self._end + len(block) - first > self.limit:
                self.error = "Transcription cannot keep up. Please stop and try a shorter recording."
                return
            self._blocks.append((self._end, block))
            self._end += len(block)
            self.level = float(np.sqrt(np.mean(block * block))) if len(block) else 0.0

    def snapshot(self, start=0.0, end=None):
        with self._lock:
            a = max(0, round(start * self.rate))
            b = self._end if end is None else min(self._end, round(end * self.rate))
            blocks = list(self._blocks)
        parts = [block[max(0, a - pos):min(len(block), b - pos)]
                 for pos, block in blocks if pos < b and pos + len(block) > a]
        return np.concatenate(parts) if parts else np.empty(0, dtype=np.float32)

    def prune(self, before):
        cutoff = int(before * self.rate)
        with self._lock:
            while self._blocks and self._blocks[0][0] + len(self._blocks[0][1]) <= cutoff:
                self._blocks.popleft()
            if self._blocks and self._blocks[0][0] < cutoff:
                pos, block = self._blocks.popleft()
                self._blocks.appendleft((cutoff, block[cutoff - pos:].copy()))


class Microphone:
    def __init__(self):
        self.stream = None
        self.buffer = None
        self._intentional_stop = False

    def prepare(self):
        import sounddevice as sd

        def callback(indata, frames, timing, status):
            buffer = self.buffer
            if buffer is not None:
                if status:
                    buffer.error = "Microphone audio was interrupted. Check the device and try again."
                buffer.append(indata[:, 0])

        def finished():
            if not self._intentional_stop and self.buffer is not None:
                self.buffer.error = "The microphone disconnected. Check it and record again."

        options = {}
        for api in sd.query_hostapis():
            if api["name"] == "Windows WASAPI" and api["default_input_device"] >= 0:
                options = dict(device=api["default_input_device"],
                               extra_settings=sd.WasapiSettings(auto_convert=True))
                break
        self.stream = sd.InputStream(samplerate=16000, channels=1,
                                     dtype="float32", blocksize=320, latency="low",
                                     callback=callback, finished_callback=finished, **options)
        logging.getLogger(__name__).info("Microphone prepared: %s, latency %.0f ms", sd.query_devices(self.stream.device)["name"], self.stream.latency * 1000)

    def start(self, buffer):
        try:
            if self.stream is None:
                self.prepare()
            self.buffer = buffer
            self._intentional_stop = False
            self.stream.start()
        except Exception:
            self.close()
            raise

    def stop(self):
        self._intentional_stop = True
        if self.stream is not None:
            self.stream.stop()
        self.buffer = None

    def close(self):
        self._intentional_stop = True
        stream, self.stream = self.stream, None
        if stream is not None:
            try:
                stream.stop()
            finally:
                stream.close()
        self.buffer = None
