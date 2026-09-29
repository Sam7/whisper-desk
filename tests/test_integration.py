"""Real Turbo test; enable explicitly to avoid surprise downloads on test runs."""
import os
from pathlib import Path

import pytest

from whisper_desk.config import Config
from whisper_desk.engine import WhisperEngine


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get("WHISPER_INTEGRATION") != "1", reason="Set WHISPER_INTEGRATION=1 for real model inference")
def test_known_jfk_audio_with_real_turbo():
    from faster_whisper.audio import decode_audio
    engine = WhisperEngine(Config())
    engine.load()
    sample = Path(__file__).parent / "data/jfk.flac"
    words, language = engine.transcribe(decode_audio(str(sample)), final=True)
    text = "".join(w.text for w in words).lower()
    assert language == "en"
    assert "my fellow americans" in text
    assert "ask not what your country can do for you" in text
    assert "ask what you can do for your country" in text
    assert engine.device in {"cuda", "cpu"}
