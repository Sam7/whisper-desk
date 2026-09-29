"""Shared executable/window identity for Windows shell integration."""
import ctypes
from importlib.resources import files
import logging
import sys

from PySide6.QtGui import QIcon

APP_ID = "WhisperDesk.Desktop"


def set_windows_app_id():
    if sys.platform == "win32":
        result = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        if result != 0:
            logging.getLogger(__name__).warning("Could not set Windows app identity: %s", result)


def application_icon():
    return QIcon(str(files("whisper_desk").joinpath("assets", "app.ico")))
