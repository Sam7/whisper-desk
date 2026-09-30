from types import SimpleNamespace

import ctranslate2
import faster_whisper
from faster_whisper import utils
import pytest

from whisper_desk.config import Config
from whisper_desk.engine import WhisperEngine


@pytest.fixture(autouse=True)
def isolate_installer_data(monkeypatch, tmp_path):
    monkeypatch.setenv("WHISPER_DESK_DATA", str(tmp_path / "installer-data"))


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


def test_installer_model_prevents_network_download(monkeypatch, tmp_path):
    from whisper_desk import engine
    monkeypatch.setattr(engine, "managed_model", lambda: tmp_path)
    monkeypatch.setattr(utils, "download_model", lambda *a, **k: pytest.fail("Installed launch must stay offline"))
    monkeypatch.setattr(ctranslate2, "get_cuda_device_count", lambda: 0)
    calls = []
    monkeypatch.setattr(faster_whisper, "WhisperModel", lambda path, **kw: calls.append(path) or object())
    monkeypatch.setattr(WhisperEngine, "_warm", lambda self: None)
    assert WhisperEngine(Config()).load()[0] == "cpu"
    assert calls == [str(tmp_path)]


def test_missing_installed_model_requests_repair_instead_of_redownload(monkeypatch, tmp_path):
    from whisper_desk import engine
    (tmp_path / "installed.json").write_text("{}")
    monkeypatch.setattr(engine, "data_root", lambda: tmp_path)
    monkeypatch.setattr(engine, "managed_model", lambda: None)
    monkeypatch.setattr(utils, "download_model", lambda *a, **k: pytest.fail("Must not download"))
    with pytest.raises(RuntimeError, match="repair"):
        WhisperEngine(Config()).load()


def test_driver_detection_exception_keeps_cpu_available(monkeypatch):
    monkeypatch.setattr(utils, "download_model", lambda *a, **k: "cache")
    monkeypatch.setattr(ctranslate2, "get_cuda_device_count", lambda: (_ for _ in ()).throw(RuntimeError("driver missing")))
    monkeypatch.setattr(faster_whisper, "WhisperModel", lambda *a, **k: object())
    monkeypatch.setattr(WhisperEngine, "_warm", lambda self: None)
    device, notice = WhisperEngine(Config()).load()
    assert device == "cpu" and "driver" in notice


def test_strict_runtime_overrides_toolkit_environment_for_cublas(monkeypatch, tmp_path):
    from whisper_desk import engine
    owned = tmp_path / "runtime/bin"
    owned.mkdir(parents=True)
    monkeypatch.setenv("WHISPER_DESK_STRICT_RUNTIME", "1")
    monkeypatch.setenv("CUDA_PATH", "C:/external-toolkit")
    monkeypatch.setenv("PATH", engine.os.environ.get("PATH", ""))
    monkeypatch.setattr(engine, "managed_runtime", lambda: owned)
    monkeypatch.setattr(engine.os, "add_dll_directory", lambda path: None)
    engine.configure_cuda_paths()
    assert engine.os.environ["CUDA_PATH"] == str(owned.parent)
    assert "external-toolkit" not in engine.os.environ["PATH"]


def test_cpu_install_preference_avoids_cuda_initialization(monkeypatch):
    from whisper_desk import engine
    monkeypatch.setattr(engine, "installed_preferences", lambda: {"gpu_enabled": False})
    monkeypatch.setattr(utils, "download_model", lambda *a, **k: "cache")
    monkeypatch.setattr(ctranslate2, "get_cuda_device_count", lambda: pytest.fail("CPU setup should not initialize CUDA"))
    monkeypatch.setattr(faster_whisper, "WhisperModel", lambda *a, **k: object())
    monkeypatch.setattr(WhisperEngine, "_warm", lambda self: None)
    assert WhisperEngine(Config()).load() == ("cpu", "")
