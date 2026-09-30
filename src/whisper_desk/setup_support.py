"""Installer diagnostics, executed before creating a QApplication."""
import ctypes
import json
import os
from pathlib import Path
import subprocess
import time

from .installation import data_root, locations, manifest, inventory_valid, stage_dependencies


def probe():
    result = dict(nvidia_present=False, cuda_available=False, driver_version=None, gpu_names=[], reason="No NVIDIA GPU detected")
    if os.name != "nt":
        return result
    command = "Get-CimInstance Win32_VideoController | Select-Object Name,AdapterCompatibility | ConvertTo-Json -Compress"
    try:
        output = subprocess.check_output(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                                         timeout=20, creationflags=subprocess.CREATE_NO_WINDOW, text=True)
        adapters = json.loads(output or "[]")
        if isinstance(adapters, dict):
            adapters = [adapters]
        result["nvidia_present"] = any("nvidia" in (a.get("Name", "") + a.get("AdapterCompatibility", "")).lower() for a in adapters)
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    try:
        # Load only the Windows driver, never a Toolkit-provided copy.
        driver = ctypes.WinDLL(str(Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/nvcuda.dll"))
        result["nvidia_present"] = True
        status = driver.cuInit(0)
        version, count = ctypes.c_int(), ctypes.c_int()
        driver.cuDriverGetVersion(ctypes.byref(version))
        result["driver_version"] = version.value
        if status != 0 or driver.cuDeviceGetCount(ctypes.byref(count)) != 0 or count.value == 0:
            raise RuntimeError("NVIDIA driver could not open the GPU")
        for index in range(count.value):
            name = ctypes.create_string_buffer(256)
            driver.cuDeviceGetName(name, len(name), index)
            result["gpu_names"].append(name.value.decode(errors="replace"))
        result["cuda_available"] = True
        result["reason"] = "CUDA driver detected; inference will be checked after download"
    except (OSError, RuntimeError) as exc:
        if result["nvidia_present"]:
            result["reason"] = f"NVIDIA driver unavailable: {exc}. Update it at https://www.nvidia.com/drivers"
    return result


def loaded_modules():
    if os.name != "nt":
        return []
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.EnumProcessModules.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    psapi.GetModuleFileNameExW.argtypes = [wintypes.HANDLE, wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
    modules = (wintypes.HMODULE * 4096)()
    needed = wintypes.DWORD()
    handle = kernel.GetCurrentProcess()
    if not psapi.EnumProcessModules(handle, modules, ctypes.sizeof(modules), ctypes.byref(needed)):
        raise OSError("Cannot inspect loaded runtime modules")
    paths = []
    for module in modules[:needed.value // ctypes.sizeof(wintypes.HMODULE)]:
        buffer = ctypes.create_unicode_buffer(32768)
        if psapi.GetModuleFileNameExW(handle, module, buffer, len(buffer)):
            paths.append(buffer.value)
    return paths


def verify(root, *, require_cuda=False, audio=None):
    os.environ["WHISPER_DESK_DATA"] = str(Path(root).resolve())
    # Strict mode also prevents source/dev CUDA paths masking an incomplete bundle.
    os.environ["WHISPER_DESK_STRICT_RUNTIME"] = "1"
    value = manifest()
    runtime, model = locations(root, value)
    if not inventory_valid(model, value["model_revision"], thorough=True):
        raise RuntimeError("Installed model is missing or damaged. Run the installer to repair it.")
    if require_cuda and not inventory_valid(runtime, value["runtime"], thorough=True):
        raise RuntimeError("Installed GPU libraries are missing or damaged")
    from .config import Config
    from .engine import WhisperEngine
    started = time.perf_counter()
    engine = WhisperEngine(Config(device="cuda" if require_cuda else "cpu"))
    engine.load()
    if require_cuda and engine.device != "cuda":
        raise RuntimeError("GPU verification failed; CPU fallback is not GPU success. Update the NVIDIA driver or install CPU mode.")
    paths = loaded_modules()
    native = [p for p in paths if Path(p).name.lower().startswith(("cudnn", "cublas", "cudart", "nvrtc", "nvjitlink"))]
    if require_cuda:
        outside = [p for p in native if not Path(p).resolve().is_relative_to(runtime.resolve())]
        if not native or outside:
            raise RuntimeError("GPU verification used libraries outside the app-owned runtime: " + "; ".join(outside))
    result = dict(device=engine.device, load_ms=round((time.perf_counter() - started) * 1000),
                  model=str(model), runtime=value["runtime"], modules=native, probe=probe())
    if audio:
        from faster_whisper.audio import decode_audio
        words, language = engine.transcribe(decode_audio(str(audio)), final=True)
        result.update(transcript="".join(w.text for w in words), language=language)
    return result


def main(command, *, root=None, cache=None, output, gpu=False, audio=None):
    started = time.perf_counter()
    result, code = {}, 0
    try:
        root = Path(root) if root else data_root()
        if command == "probe":
            result = probe()
            code = 0 if result["cuda_available"] else 11 if result["nvidia_present"] else 10
        elif command == "stage":
            if not cache:
                raise ValueError("Setup cache is required")
            runtime, model = stage_dependencies(root, cache, manifest(), gpu=gpu,
                                                cancelled=lambda: (root / "setup.cancel").exists())
            result = dict(runtime=str(runtime), model=str(model))
        elif command == "verify":
            result = verify(root, require_cuda=gpu, audio=audio)
        else:
            raise ValueError("Unknown setup command")
        if command != "probe" and (root / "setup.cancel").exists():
            raise InterruptedError("Setup cancelled")
    except Exception as exc:
        result = dict(error=str(exc))
        code = 1
    result.update(elapsed_ms=round((time.perf_counter() - started) * 1000), exit_code=code)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return code
