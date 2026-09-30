"""Audit x64 runtime DLL import closure against the app and Windows system files."""
import argparse
import json
import os
from pathlib import Path

import pefile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify-cudnn", action="store_true", help="Also exercise the native cuDNN API on the NVIDIA GPU")
    args = parser.parse_args()
    system = Path(os.environ["SystemRoot"]) / "System32"
    available = {p.name.lower() for directory in (args.runtime, args.app, args.app / "_internal", system)
                 for p in directory.glob("*.dll")}
    report = []
    for path in sorted(args.runtime.glob("*.dll")):
        with pefile.PE(str(path), fast_load=True) as binary:
            binary.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"],
                                                       pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT"]])
            imports = [e.dll.decode().lower() for e in getattr(binary, "DIRECTORY_ENTRY_IMPORT", []) +
                       getattr(binary, "DIRECTORY_ENTRY_DELAY_IMPORT", [])]
            missing = [name for name in imports if name not in available and not name.startswith(("api-ms-", "ext-ms-"))]
            report.append(dict(file=path.name, x64=binary.FILE_HEADER.Machine == 0x8664, imports=imports, missing=missing))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if not report or any(not r["x64"] or r["missing"] for r in report):
        raise SystemExit("Runtime import audit failed; inspect " + str(args.output))
    print(f"Audited {len(report)} x64 runtime DLLs: all static and delay imports resolve")
    if args.verify_cudnn:
        import ctypes
        from whisper_desk.setup_support import loaded_modules
        runtime = args.runtime.resolve()
        os.environ["CUDA_PATH"] = str(runtime.parent)
        os.environ["PATH"] = str(runtime) + os.pathsep + str(system)
        directory = os.add_dll_directory(str(runtime))
        cuda = ctypes.WinDLL(str(runtime / "cudart64_12.dll"))
        if cuda.cudaSetDevice(0) != 0:
            raise SystemExit("CUDA runtime could not initialize GPU 0")
        cudnn = ctypes.WinDLL(str(runtime / "cudnn64_9.dll"))
        cudnn.cudnnGetVersion.restype = ctypes.c_size_t
        handle = ctypes.c_void_p()
        if cudnn.cudnnCreate(ctypes.byref(handle)) != 0:
            raise SystemExit("cuDNN could not create a GPU handle")
        if cudnn.cudnnDestroy(handle) != 0:
            raise SystemExit("cuDNN handle cleanup failed")
        paths = [p for p in loaded_modules() if Path(p).name.lower().startswith(("cudnn", "cublas", "cudart", "nvrtc", "nvjitlink"))]
        if not paths or any(not Path(p).resolve().is_relative_to(runtime) for p in paths):
            raise SystemExit("Native cuDNN check used libraries outside the owned runtime")
        native = dict(version=cudnn.cudnnGetVersion(), create_destroy="passed", modules=paths)
        args.output.with_name(args.output.stem + "-cudnn.json").write_text(json.dumps(native, indent=2), encoding="utf-8")
        print(f"Native cuDNN {native['version']} GPU handle check passed with app-owned libraries")


if __name__ == "__main__":
    main()
