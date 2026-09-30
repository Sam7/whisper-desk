"""Resident faster-whisper engine. Deliberately independent of Qt."""
import logging
import os
from pathlib import Path
import sys
from time import perf_counter

import numpy as np

from .models import Word
from .installation import SetupRepairRequired, data_root, installed_preferences, managed_model, managed_runtime

log = logging.getLogger(__name__)
_dll_handles = []


def configure_cuda_paths():
    """Make installed NVIDIA DLLs discoverable, including optional pip wheels."""
    if os.name != "nt":
        return
    owned = managed_runtime()
    strict = bool(getattr(sys, "frozen", False) or os.environ.get("WHISPER_DESK_STRICT_RUNTIME"))
    if owned:
        os.environ["PATH"] = str(owned) + os.pathsep + os.environ.get("PATH", "")
        _dll_handles.append(os.add_dll_directory(str(owned)))
    if strict:
        # Native LoadLibrary calls must not find an incidental developer Toolkit.
        windows = Path(os.environ.get("SystemRoot", "C:/Windows"))
        os.environ["PATH"] = os.pathsep.join(str(p) for p in (owned, windows / "System32", windows) if p)
        # CTranslate2's cuBLAS loader explicitly reads CUDA_PATH and calls
        # SetDllDirectory, overriding PATH/AddDllDirectory. Keep it app-local too.
        if owned:
            os.environ["CUDA_PATH"] = str(owned.parent)
        else:
            os.environ.pop("CUDA_PATH", None)
        return
    roots = [Path(os.environ.get("CUDA_PATH", "C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v12.9")) / "bin"]
    roots += [Path(sys.prefix) / "Lib/site-packages/nvidia" / name / "bin"
              for name in ("cublas", "cudnn", "cuda_runtime")]
    # NVIDIA's official Windows cuDNN installer uses a separate directory.
    cudnn_root = Path("C:/Program Files/NVIDIA/CUDNN")
    if cudnn_root.exists():
        roots += sorted(cudnn_root.glob("v9*/bin/12*"))
    roots += [Path(sys._MEIPASS)] if hasattr(sys, "_MEIPASS") else []
    extra = os.environ.get("WHISPER_CUDA_PATH")
    if extra:
        roots.insert(0, Path(extra))
    for path in roots:
        if path.is_dir():
            os.environ["PATH"] = str(path) + os.pathsep + os.environ.get("PATH", "")
            _dll_handles.append(os.add_dll_directory(str(path)))


class WhisperEngine:
    def __init__(self, config):
        self.config = config
        self.model = None
        self.device = None
        self.notice = ""

    def load(self):
        configure_cuda_paths()
        from faster_whisper import WhisperModel
        from faster_whisper.utils import download_model
        import ctranslate2
        started = perf_counter()
        installed = managed_model() if self.config.model == "turbo" else None
        if installed:
            model_path = str(installed)
        elif (data_root() / "installed.json").exists():
            raise SetupRepairRequired("The Whisper model is missing or damaged. Run the installer again to repair it.")
        else:
            try:
                model_path = download_model(self.config.model, local_files_only=True)
            except Exception:
                model_path = self.config.model  # Source/portable first launch can download.
        try:
            wanted = self.config.device == "cuda" or (self.config.device == "auto" and
                                                       installed_preferences().get("gpu_enabled", True))
            available = wanted and ctranslate2.get_cuda_device_count()
        except Exception:
            log.exception("NVIDIA driver detection failed; using CPU")
            available = False
            self.notice = "NVIDIA driver unavailable. Using CPU."
        preferred = "cuda" if available else "cpu"
        try:
            self.model = WhisperModel(model_path, device=preferred,
                                      compute_type="float16" if preferred == "cuda" else "int8",
                                      cpu_threads=4, num_workers=1)
            self.device = preferred
            self._warm()
        except Exception:
            if preferred != "cuda":
                raise
            log.exception("CUDA initialization failed; falling back to CPU")
            self.model = None
            self.model = WhisperModel(model_path, device="cpu", compute_type="int8", cpu_threads=4)
            self.device = "cpu"
            self.notice = "CUDA could not start. Using CPU. See the log for details."
            self._warm()
        log.info("Model loaded and warmed: %.0f ms (%s)", (perf_counter() - started) * 1000, self.device)
        return self.device, self.notice

    def _warm(self):
        # Run the encoder AND decoder; VAD must not bypass warm-up.
        segments, _ = self.model.transcribe(np.zeros(16000, np.float32), language="en",
                                           beam_size=1, vad_filter=False)
        list(segments)
        from faster_whisper.vad import get_speech_timestamps
        get_speech_timestamps(np.zeros(16000, np.float32))

    def transcribe(self, audio, *, final=False, language=None):
        if not self.has_speech(audio):
            return [], language or self.config.language
        segments, info = self.model.transcribe(
            audio, language=language or self.config.language, beam_size=3,
            word_timestamps=True, condition_on_previous_text=False,
            temperature=(0.0, 0.2) if final else 0.0, max_new_tokens=192,
            vad_filter=True,
            vad_parameters={"min_speech_duration_ms": 100, "min_silence_duration_ms": 350,
                            "speech_pad_ms": 250},
        )
        words = [Word(w.start, w.end, w.word) for s in segments for w in (s.words or [])]
        return words, info.language

    def has_speech(self, audio):
        from faster_whisper.vad import get_speech_timestamps
        return bool(get_speech_timestamps(audio, min_speech_duration_ms=100))
