"""Capture one Windows window, including its frame, without capturing the desktop."""
import ctypes
from ctypes import wintypes

from PySide6.QtGui import QImage


class BitmapHeader(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("width", wintypes.LONG), ("height", wintypes.LONG),
                ("planes", wintypes.WORD), ("bits", wintypes.WORD), ("compression", wintypes.DWORD),
                ("image_size", wintypes.DWORD), ("xppm", wintypes.LONG), ("yppm", wintypes.LONG),
                ("used", wintypes.DWORD), ("important", wintypes.DWORD)]


def capture_window(hwnd, path):
    user, gdi = ctypes.windll.user32, ctypes.windll.gdi32
    user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user.GetDC.argtypes = [wintypes.HWND]
    user.GetDC.restype = wintypes.HDC
    user.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
    gdi.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi.CreateCompatibleDC.restype = wintypes.HDC
    gdi.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.UINT,
                                   ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD]
    gdi.CreateDIBSection.restype = wintypes.HBITMAP
    gdi.SelectObject.argtypes = [wintypes.HDC, wintypes.HANDLE]
    gdi.SelectObject.restype = wintypes.HANDLE
    gdi.DeleteObject.argtypes = [wintypes.HANDLE]
    gdi.DeleteDC.argtypes = [wintypes.HDC]
    rect = wintypes.RECT()
    if not user.GetWindowRect(hwnd, ctypes.byref(rect)):
        raise OSError("Cannot read the window bounds")
    width, height = rect.right - rect.left, rect.bottom - rect.top
    header = BitmapHeader(ctypes.sizeof(BitmapHeader), width, -height, 1, 32, 0, width * height * 4)
    bits = ctypes.c_void_p()
    screen_dc = user.GetDC(hwnd)
    memory_dc = gdi.CreateCompatibleDC(screen_dc)
    bitmap = gdi.CreateDIBSection(screen_dc, ctypes.byref(header), 0, ctypes.byref(bits), None, 0)
    previous = gdi.SelectObject(memory_dc, bitmap)
    try:
        if not bits.value or not user.PrintWindow(hwnd, memory_dc, 2):
            raise OSError("Windows could not render the window")
        data = ctypes.string_at(bits, width * height * 4)
        if not QImage(data, width, height, width * 4, QImage.Format.Format_RGB32).save(str(path)):
            raise OSError("Cannot save the window capture")
    finally:
        gdi.SelectObject(memory_dc, previous)
        gdi.DeleteObject(bitmap)
        gdi.DeleteDC(memory_dc)
        user.ReleaseDC(hwnd, screen_dc)
