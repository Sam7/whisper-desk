"""Capture a supplied setup HWND without including any other desktop windows."""
import argparse
from pathlib import Path
from PySide6.QtWidgets import QApplication
from capture_native import capture_window

parser = argparse.ArgumentParser()
parser.add_argument("hwnd", type=int)
parser.add_argument("output", type=Path)
args = parser.parse_args()
app = QApplication([])
args.output.parent.mkdir(parents=True, exist_ok=True)
capture_window(args.hwnd, args.output)
