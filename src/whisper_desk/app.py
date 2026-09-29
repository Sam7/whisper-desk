import argparse
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys

from PySide6.QtWidgets import QApplication

from .config import Config
from .branding import application_icon, set_windows_app_id
from .session import SessionService
from .ui import Bridge, MainWindow


def setup_logging():
    folder = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "WhisperDesk" / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    handlers = [RotatingFileHandler(folder / "app.log", maxBytes=2_000_000, backupCount=2, encoding="utf-8")]
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", handlers=handlers)


def main():
    parser = argparse.ArgumentParser(description="Whisper Desk — local voice transcription")
    parser.add_argument("--version", action="version", version="Whisper Desk 0.1.0")
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    parser.add_argument("--language", default=None, help="Optional language code, e.g. en; default auto-detect")
    parser.add_argument("--verify-audio", help=argparse.SUPPRESS)
    parser.add_argument("--verify-output", default="artifacts/packaged", help=argparse.SUPPRESS)
    parser.add_argument("--verify-theme", choices=["system", "light", "dark"], default="system", help=argparse.SUPPRESS)
    parser.add_argument("--verify-sessions", type=int, default=1, help=argparse.SUPPRESS)
    args = parser.parse_args()
    set_windows_app_id()
    if args.verify_audio:
        from .diagnostics import main as verify
        verify(["--audio", args.verify_audio, "--output", args.verify_output, "--theme", args.verify_theme,
                "--sessions", str(args.verify_sessions)])
        return 0
    setup_logging()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Whisper Desk")
    app.setOrganizationName("WhisperDesk")
    app.setWindowIcon(application_icon())
    app.setStyle("Fusion")
    bridge = Bridge()
    service = SessionService(bridge.event.emit, Config(device=args.device, language=args.language))
    window = MainWindow(service)
    bridge.event.connect(window.handle)
    window.show()
    service.launch()
    try:
        return app.exec()
    finally:
        service.close()
        service.join(1)


if __name__ == "__main__":
    raise SystemExit(main())
