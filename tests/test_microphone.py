from types import SimpleNamespace

import numpy as np
import pytest
import sounddevice

from whisper_desk.audio import AudioBuffer, Microphone


class Stream:
    def __init__(self, **options):
        self.options = options
        self.device = options["device"]
        self.latency = 0.04
        self.closed = False

    def start(self):
        self.options["callback"](np.ones((320, 1), np.float32), 320, None, False)

    def stop(self):
        self.options["finished_callback"]()

    def close(self):
        self.closed = True


@pytest.fixture
def mocked_sd(monkeypatch):
    monkeypatch.setattr(sounddevice, "query_hostapis", lambda: [{"name": "Windows WASAPI", "default_input_device": 7}])
    monkeypatch.setattr(sounddevice, "query_devices", lambda device: {"name": "Mock microphone"})
    monkeypatch.setattr(sounddevice, "InputStream", Stream)


def test_prepared_wasapi_stream_is_reused_and_closed(mocked_sd):
    mic = Microphone()
    mic.prepare()
    stream = mic.stream
    assert stream.options["device"] == 7
    for _ in range(2):
        buffer = AudioBuffer()
        mic.start(buffer)
        mic.stop()
        assert buffer.end == 0.02 and buffer.error is None
        assert mic.stream is stream
    mic.close()
    assert stream.closed and mic.stream is None


def test_unexpected_finished_callback_reports_disconnect(mocked_sd):
    mic, buffer = Microphone(), AudioBuffer()
    mic.start(buffer)
    mic.stream.options["finished_callback"]()
    assert "disconnected" in buffer.error
    mic.close()


def test_audio_overflow_is_reported(mocked_sd):
    mic, buffer = Microphone(), AudioBuffer()
    mic.start(buffer)
    mic.stream.options["callback"](np.ones((320, 1)), 320, None, True)
    assert "interrupted" in buffer.error
    mic.close()
