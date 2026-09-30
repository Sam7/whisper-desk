"""Verified app-owned model/runtime files. No Qt or Whisper imports."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from urllib.parse import urlparse
from urllib.request import urlopen
import zipfile


class SetupRepairRequired(RuntimeError):
    """A concise error that the session can show directly to the user."""


def data_root():
    return Path(os.environ.get("WHISPER_DESK_DATA", Path(os.environ.get("LOCALAPPDATA", Path.home())) / "WhisperDesk"))


def manifest():
    value = json.loads((Path(__file__).parent / "assets/setup-dependencies.json").read_text(encoding="utf-8"))
    validate_manifest(value)
    return value


def validate_manifest(value):
    if value.get("schema") != 1:
        raise ValueError("Unsupported setup manifest")
    for key in ("runtime", "model_revision"):
        if not re.fullmatch(r"[a-zA-Z0-9.-]+", value.get(key, "")):
            raise ValueError("Invalid dependency identifier")
    seen = set()
    for item in value["downloads"]:
        url = urlparse(item["url"])
        expected_host = "developer.download.nvidia.com" if item["kind"] == "gpu" else "huggingface.co"
        if item["kind"] not in ("gpu", "model") or url.scheme != "https" or url.hostname != expected_host:
            raise ValueError("Dependency must use an official HTTPS URL")
        if not re.fullmatch(r"[a-zA-Z0-9_.-]+", item["name"]) or item["name"] in seen:
            raise ValueError("Invalid or duplicate dependency name")
        seen.add(item["name"])
        if not re.fullmatch(r"[a-f0-9]{64}", item["sha256"]) or item["size"] <= 0:
            raise ValueError("Missing dependency size or SHA-256")
    required = {"model.bin", "config.json", "preprocessor_config.json", "tokenizer.json", "vocabulary.json"}
    if {d["name"] for d in value["downloads"] if d["kind"] == "model"} != required:
        raise ValueError("Incomplete Turbo model manifest")


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def installed_preferences():
    try:
        value = json.loads((data_root() / "installed.json").read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def copy_checked(stream, output, cancelled):
    while True:
        if cancelled():
            raise InterruptedError("Setup cancelled")
        block = stream.read(1024 * 1024)
        if not block:
            break
        output.write(block)


def cache_name(item):
    return item["sha256"] + (".zip" if item["kind"] == "gpu" else ".model")


def matches(path, item):
    path = Path(path)
    return path.is_file() and path.stat().st_size == item["size"] and digest(path) == item["sha256"]


def acquire(item, cache, *, opener=urlopen, cancelled=lambda: False, progress=lambda done, total: None):
    """Retry reuses complete verified files; partial files are never reused."""
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / cache_name(item)
    if matches(target, item):
        return target
    partial = target.with_suffix(target.suffix + ".partial")
    try:
        if shutil.disk_usage(cache).free < item["size"] + 64 * 1024**2:
            raise OSError("Not enough disk space for this download")
        with opener(item["url"], timeout=60) as response, partial.open("wb") as output:
            done = 0
            while True:
                if cancelled():
                    raise InterruptedError("Setup cancelled")
                block = response.read(1024 * 1024)
                if not block:
                    break
                done += len(block)
                if done > item["size"]:
                    raise ValueError("Download exceeds its expected size")
                output.write(block)
                progress(done, item["size"])
        if not matches(partial, item):
            raise ValueError(f"Download verification failed: {item['name']}")
        partial.replace(target)
        return target
    finally:
        partial.unlink(missing_ok=True)


def locations(root, value):
    root = Path(root)
    return root / "runtime" / value["runtime"], root / "models" / "turbo" / value["model_revision"]


def inventory_valid(folder, identity, *, thorough=False):
    folder = Path(folder)
    try:
        inventory = json.loads((folder / "ready.json").read_text(encoding="utf-8"))
        if inventory["identity"] != identity or not inventory["files"]:
            return False
        for item in inventory["files"]:
            name = PurePosixPath(item["name"])
            if name.is_absolute() or ".." in name.parts or "\\" in str(name) or ":" in str(name):
                return False
            path = folder / str(name)
            if not path.is_file() or path.stat().st_size != item["size"]:
                return False
            if thorough and digest(path) != item["sha256"]:
                return False
        return True
    except (OSError, ValueError, KeyError, TypeError):
        return False


def _seal(folder, identity):
    files = [dict(name=p.relative_to(folder).as_posix(), size=p.stat().st_size, sha256=digest(p))
             for p in sorted(folder.rglob("*")) if p.is_file()]
    (folder / "ready.json").write_text(json.dumps(dict(identity=identity, files=files), indent=2), encoding="utf-8")


def _activate(staged, target):
    # Preserve a damaged/old directory until the verified replacement is active.
    backup = target.with_name(target.name + ".previous")
    if backup.exists():
        shutil.rmtree(backup)
    if target.exists():
        target.rename(backup)
    try:
        staged.rename(target)
    except Exception:
        if backup.exists():
            backup.rename(target)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def stage_dependencies(root, cache, value, *, gpu=True, cancelled=lambda: False):
    """Build verified versioned directories without importing native GPU libraries."""
    validate_manifest(value)
    root, cache = Path(root), Path(cache)
    root.mkdir(parents=True, exist_ok=True)
    runtime, model = locations(root, value)
    selected = [d for d in value["downloads"] if gpu or d["kind"] == "model"]
    # Conservative upper bound for ZIP expansion, staging and model copies.
    required = sum(d["size"] * (8 if d["kind"] == "gpu" else 2) for d in selected)
    if shutil.disk_usage(root).free < required + 256 * 1024**2:
        raise OSError("Not enough disk space to stage transcription dependencies")
    for kind, target, identity in (("model", model, value["model_revision"]), ("gpu", runtime, value["runtime"])):
        if kind == "gpu" and not gpu:
            continue
        if inventory_valid(target, identity, thorough=True):
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".setup-", dir=target.parent) as temporary:
            staged = Path(temporary) / "ready"
            staged.mkdir()
            for item in selected:
                if item["kind"] != kind:
                    continue
                if cancelled():
                    raise InterruptedError("Setup cancelled")
                source = cache / cache_name(item)
                if not matches(source, item):
                    raise ValueError(f"Missing or damaged download: {item['name']}")
                if kind == "model":
                    with source.open("rb") as stream, (staged / item["name"]).open("wb") as output:
                        copy_checked(stream, output, cancelled)
                    continue
                with zipfile.ZipFile(source) as archive:
                    entries = archive.infolist()
                    if sum(e.file_size for e in entries) > item["size"] * 8:
                        raise ValueError("Runtime archive exceeds its expansion limit")
                    for entry in entries:
                        name = PurePosixPath(entry.filename)
                        if name.is_absolute() or ".." in name.parts or "\\" in entry.filename or ":" in entry.filename:
                            raise ValueError("Unsafe runtime archive path")
                        if entry.is_dir():
                            continue
                        if name.suffix.lower() == ".dll" and "bin" in name.parts:
                            destination = staged / "bin" / name.name
                        elif name.name.upper().startswith(("LICENSE", "EULA")):
                            destination = staged / "licenses" / item["name"] / name.name
                        else:
                            continue
                        if destination.exists():
                            raise ValueError(f"Duplicate runtime file: {name.name}")
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        with archive.open(entry) as stream, destination.open("wb") as output:
                            copy_checked(stream, output, cancelled)
            if kind == "gpu" and not all((staged / "bin" / name).is_file() for name in
                                        ("cublas64_12.dll", "cublasLt64_12.dll", "cudnn64_9.dll", "cudart64_12.dll")):
                raise ValueError("Runtime archive set is missing required DLLs")
            if cancelled():
                raise InterruptedError("Setup cancelled")
            _seal(staged, identity)
            _activate(staged, target)
    return runtime, model


def managed_model(root=None):
    value = manifest()
    _, model = locations(root or data_root(), value)
    if inventory_valid(model, value["model_revision"]):
        return model
    return None


def managed_runtime(root=None):
    value = manifest()
    runtime, _ = locations(root or data_root(), value)
    return runtime / "bin" if inventory_valid(runtime, value["runtime"]) else None
