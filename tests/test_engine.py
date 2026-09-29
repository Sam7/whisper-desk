from types import SimpleNamespace

import ctranslate2
import faster_whisper
from faster_whisper import utils
import pytest

from whisper_desk.config import Config
from whisper_desk.engine import WhisperEngine


@pytest.mark.parametrize("cuda_count,device,compute", [(1, "cuda", "float16"), (0, "cpu", "int8")])
def test_backend_selection_and_cache(monkeypatch, cuda_count, device, compute):
    calls = []
    monkeypatch.setattr(ctranslate2, "get_cuda_device_count", lambda: cuda_count)
    monkeypatch.setattr(utils, "download_model", lambda model, **kw: "cached-turbo")
    monkeypatch.setattr(faster_whisper, "WhisperModel", lambda model, **kw: calls.append((model, kw)) or object())
    monkeypatch.setattr(WhisperEngine, "_warm", lambda self: None)
    e = WhisperEngine(Config())
    assert e.load() == (device, "")
    assert calls[0][0] == "cached-turbo"
    assert calls[0][1]["compute_type"] == compute


def test_cuda_warmup_failure_falls_back_to_cpu(monkeypatch):
    calls = []
    monkeypatch.setattr(ctranslate2, "get_cuda_device_count", lambda: 1)
    monkeypatch.setattr(utils, "download_model", lambda *a, **k: "cache")
    monkeypatch.setattr(faster_whisper, "WhisperModel", lambda *a, **kw: calls.append(kw["device"]) or object())

    def warm(self):
        if self.device == "cuda":
            raise RuntimeError("cuDNN DLL missing")

    monkeypatch.setattr(WhisperEngine, "_warm", warm)
    e = WhisperEngine(Config())
    backend, notice = e.load()
    assert backend == "cpu" and "CPU" in notice
    assert calls == ["cuda", "cpu"]


def test_cpu_load_failure_propagates(monkeypatch):
    monkeypatch.setattr(ctranslate2, "get_cuda_device_count", lambda: 0)
    monkeypatch.setattr(utils, "download_model", lambda *a, **k: "cache")

    def fail(*a, **kw):
        raise RuntimeError("missing model")

    monkeypatch.setattr(faster_whisper, "WhisperModel", fail)
    with pytest.raises(RuntimeError, match="missing model"):
        WhisperEngine(Config()).load()
