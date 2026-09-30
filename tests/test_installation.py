import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest

from whisper_desk import installation as setup


def item(name, data, kind="model"):
    host = "developer.download.nvidia.com" if kind == "gpu" else "huggingface.co"
    return dict(name=name, kind=kind, url=f"https://{host}/{name}", size=len(data), sha256=hashlib.sha256(data).hexdigest())


@pytest.fixture
def locked(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    downloads = []
    for name in ("model.bin", "config.json", "preprocessor_config.json", "tokenizer.json", "vocabulary.json"):
        data = ("fixture " + name).encode()
        value = item(name, data)
        (cache / setup.cache_name(value)).write_bytes(data)
        downloads.append(value)
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as output:
        for name in ("cublas64_12.dll", "cublasLt64_12.dll", "cudnn64_9.dll", "cudart64_12.dll"):
            output.writestr("runtime/bin/" + name, b"fake DLL for hardware-free tests")
        output.writestr("runtime/LICENSE.txt", "Fixture licence")
        output.writestr("runtime/include/header.h", "Do not install development files")
    value = item("runtime", archive.getvalue(), "gpu")
    (cache / setup.cache_name(value)).write_bytes(archive.getvalue())
    downloads.append(value)
    return dict(schema=1, runtime="runtime-v1", model_revision="revision-v1", downloads=downloads), cache


def test_release_lock_is_complete_and_pinned():
    value = setup.manifest()
    assert len(value["downloads"]) == 10
    assert value["model_revision"] == "0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf"
    assert {d["name"] for d in value["downloads"] if d["kind"] == "gpu"} == {
        "cuda_cudart", "libcublas", "cuda_nvrtc", "libnvjitlink", "cudnn"}


@pytest.mark.parametrize("field,bad", [("url", "http://huggingface.co/model"), ("url", "https://evil.example/model"),
                                       ("sha256", "missing"), ("name", "../model.bin"), ("size", 0)])
def test_manifest_rejects_untrusted_or_incomplete_downloads(locked, field, bad):
    value, _ = locked
    value["downloads"][0][field] = bad
    with pytest.raises(ValueError):
        setup.validate_manifest(value)


def test_download_reuses_only_verified_complete_files(tmp_path):
    data = b"test download"
    value = item("model.bin", data)
    calls = []
    def open_file(*args, **kwargs):
        calls.append(args)
        return io.BytesIO(data)
    path = setup.acquire(value, tmp_path, opener=open_file)
    assert path.read_bytes() == data
    assert setup.acquire(value, tmp_path, opener=open_file) == path
    assert len(calls) == 1
    path.write_bytes(b"corrupted")
    setup.acquire(value, tmp_path, opener=open_file)
    assert len(calls) == 2 and path.read_bytes() == data


def test_bad_checksum_and_cancel_never_activate_a_partial_download(tmp_path):
    value = item("model.bin", b"expected")
    with pytest.raises(ValueError, match="verification"):
        setup.acquire(value, tmp_path, opener=lambda *a, **k: io.BytesIO(b"damaged!"))
    with pytest.raises(InterruptedError):
        setup.acquire(value, tmp_path, opener=lambda *a, **k: io.BytesIO(b"expected"), cancelled=lambda: True)
    assert not list(tmp_path.glob("*.partial"))
    assert not (tmp_path / setup.cache_name(value)).exists()


def test_low_disk_space_stops_before_downloading(tmp_path, monkeypatch):
    monkeypatch.setattr(setup.shutil, "disk_usage", lambda path: SimpleNamespace(free=0))
    with pytest.raises(OSError, match="disk space"):
        setup.acquire(item("model.bin", b"sample"), tmp_path, opener=lambda *a, **k: pytest.fail("Should not download"))


def test_stage_seals_runtime_and_model_and_preserves_repeated_install(locked, tmp_path, monkeypatch):
    value, cache = locked
    root = tmp_path / "data with spaces"
    runtime, model = setup.stage_dependencies(root, cache, value)
    assert (runtime / "bin/cudnn64_9.dll").is_file()
    assert (runtime / "licenses/runtime/LICENSE.txt").is_file()
    assert not list(runtime.rglob("*.h"))
    assert setup.inventory_valid(model, value["model_revision"], thorough=True)
    stamp = (model / "ready.json").stat().st_mtime_ns
    setup.stage_dependencies(root, cache, value)
    assert (model / "ready.json").stat().st_mtime_ns == stamp
    monkeypatch.setattr(setup, "manifest", lambda: value)
    assert setup.managed_model(root) == model
    assert setup.managed_runtime(root) == runtime / "bin"
    (model / "config.json").unlink()
    assert setup.managed_model(root) is None
    setup.stage_dependencies(root, cache, value)
    assert setup.managed_model(root) == model


def test_failed_model_stage_does_not_replace_existing_model(locked, tmp_path):
    value, cache = locked
    root = tmp_path / "data"
    _, model = setup.stage_dependencies(root, cache, value, gpu=False)
    original = (model / "model.bin").read_bytes()
    (model / "ready.json").unlink()
    (cache / setup.cache_name(value["downloads"][0])).write_bytes(b"bad")
    with pytest.raises(ValueError, match="damaged"):
        setup.stage_dependencies(root, cache, value, gpu=False)
    assert (model / "model.bin").read_bytes() == original
    assert not list(model.parent.glob(".setup-*"))


def test_unsafe_zip_entry_is_rejected_before_activation(locked, tmp_path):
    value, cache = locked
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("../escape.dll", b"bad")
    bad = item("runtime", stream.getvalue(), "gpu")
    value["downloads"][-1] = bad
    (cache / setup.cache_name(bad)).write_bytes(stream.getvalue())
    with pytest.raises(ValueError, match="Unsafe"):
        setup.stage_dependencies(tmp_path / "data", cache, value)
    assert not (tmp_path / "escape.dll").exists()
    runtime, _ = setup.locations(tmp_path / "data", value)
    assert not runtime.exists()


def test_cancel_during_staging_leaves_no_active_or_partial_model(locked, tmp_path):
    value, cache = locked
    root = tmp_path / "data"
    calls = []
    def cancelled():
        calls.append(True)
        return len(calls) >= 2
    with pytest.raises(InterruptedError):
        setup.stage_dependencies(root, cache, value, gpu=False, cancelled=cancelled)
    _, model = setup.locations(root, value)
    assert not model.exists()
    assert not list(model.parent.glob(".setup-*"))


def test_setup_command_reports_failures_as_json(tmp_path, monkeypatch):
    from whisper_desk import setup_support
    monkeypatch.setattr(setup_support, "verify", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("missing model")))
    output = tmp_path / "result.json"
    assert setup_support.main("verify", root=tmp_path, output=output, gpu=True) == 1
    assert json.loads(output.read_text())["error"] == "missing model"


def test_strict_verification_rejects_cpu_fallback(locked, tmp_path, monkeypatch):
    from whisper_desk import setup_support
    from whisper_desk.engine import WhisperEngine
    value, cache = locked
    root = tmp_path / "data"
    setup.stage_dependencies(root, cache, value)
    monkeypatch.setattr(setup_support, "manifest", lambda: value)
    monkeypatch.setenv("WHISPER_DESK_DATA", str(root))
    monkeypatch.setenv("WHISPER_DESK_STRICT_RUNTIME", "1")
    def cpu_load(self):
        self.device = "cpu"
    monkeypatch.setattr(WhisperEngine, "load", cpu_load)
    with pytest.raises(RuntimeError, match="CPU fallback"):
        setup_support.verify(root, require_cuda=True)
