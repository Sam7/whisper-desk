import argparse
import logging
from logging.handlers import RotatingFileHandler
import json
import os
from pathlib import Path
import sys


def setup_logging():
    folder = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "WhisperDesk" / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    handlers = [RotatingFileHandler(folder / "app.log", maxBytes=2_000_000, backupCount=2, encoding="utf-8")]
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", handlers=handlers)


def application_version():
    """Read the version embedded by the release build; source installs use package metadata."""
    try:
        if getattr(sys, "frozen", False):
            version_file = Path(sys._MEIPASS) / "whisper_desk" / "assets" / "release-version.json"
            version = json.loads(version_file.read_text(encoding="utf-8"))["version"]
        else:
            from importlib.metadata import version as distribution_version
            version = distribution_version("whisper-desk")
        if not isinstance(version, str) or not version:
            raise ValueError("Invalid packaged application version")
        return version
    except (OSError, ValueError, KeyError, TypeError, LookupError):
        return "development"


def main():
    parser = argparse.ArgumentParser(description="Whisper Desk — local voice transcription")
    parser.add_argument("--version", action="version", version=f"WhisperDesk {application_version()}")
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    parser.add_argument("--language", default=None, help="Optional language code, e.g. en; default auto-detect")
    parser.add_argument("--verify-audio", help=argparse.SUPPRESS)
    parser.add_argument("--verify-output", default="artifacts/packaged", help=argparse.SUPPRESS)
    parser.add_argument("--verify-theme", choices=["system", "light", "dark"], default="system", help=argparse.SUPPRESS)
    parser.add_argument("--verify-sessions", type=int, default=1, help=argparse.SUPPRESS)
    parser.add_argument("--setup-probe", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--setup-stage", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--setup-verify", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--setup-root", help=argparse.SUPPRESS)
    parser.add_argument("--setup-cache", help=argparse.SUPPRESS)
    parser.add_argument("--setup-output", help=argparse.SUPPRESS)
    parser.add_argument("--require-cuda", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--setup-audio", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.setup_probe or args.setup_stage or args.setup_verify:
        if not args.setup_output:
            parser.error("Setup commands require --setup-output")
        from .setup_support import main as setup
        command = "probe" if args.setup_probe else "stage" if args.setup_stage else "verify"
        return setup(command, root=args.setup_root, cache=args.setup_cache, output=args.setup_output,
                     gpu=args.require_cuda, audio=args.setup_audio)
    from PySide6.QtWidgets import QApplication
    from .config import Config
    from .branding import application_icon, set_windows_app_id
    from .session import SessionService
    from .ui import Bridge, MainWindow
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
