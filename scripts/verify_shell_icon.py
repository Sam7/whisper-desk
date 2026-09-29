"""Extract the actual EXE icons through Windows and capture them for inspection."""
import ctypes
from pathlib import Path

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication


def main():
    app = QApplication([])
    executable = Path("dist/WhisperDesk/WhisperDesk.exe").resolve()
    output = Path("artifacts/shell-icon")
    output.mkdir(parents=True, exist_ok=True)
    large, small = ctypes.c_void_p(), ctypes.c_void_p()
    extract = ctypes.windll.shell32.ExtractIconExW
    extract.argtypes = [ctypes.c_wchar_p, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p),
                       ctypes.POINTER(ctypes.c_void_p), ctypes.c_uint]
    count = extract(str(executable), 0, ctypes.byref(large), ctypes.byref(small), 1)
    if count < 1 or not large.value or not small.value:
        raise RuntimeError("Windows could not extract the executable icon")
    destroy = ctypes.windll.user32.DestroyIcon
    destroy.argtypes = [ctypes.c_void_p]
    try:
        for name, handle in (("large", large), ("small", small)):
            image = QImage.fromHICON(handle.value)
            if image.isNull():
                raise RuntimeError(f"Windows returned an empty {name} icon")
            image.save(str(output / f"{name}.png"))
            print(f"Windows {name} icon: {image.width()}×{image.height()}")
    finally:
        destroy(large)
        destroy(small)


if __name__ == "__main__":
    main()
