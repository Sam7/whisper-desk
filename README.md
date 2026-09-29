# Whisper Desk — Free, Private Offline Voice Transcription

**Turn your voice into text on your own computer. No cloud subscription, no account, no per-minute fees.**

Whisper Desk is a free desktop speech-to-text app for **Windows 11**, powered by **OpenAI Whisper Turbo**. It delivers high-quality local audio transcription in a simple native interface: press Record, speak naturally, watch your words appear, and press Finish. Copy the text into your notes, emails, documents or favourite app.

Your audio stays on your computer. After the initial model download, transcription works **offline**, without sending recordings to a cloud transcription service or requiring an OpenAI API key.

## Light and dark mode

<table>
  <tr>
    <th>Light mode · completed transcription</th>
    <th>Dark mode · transcribing as you talk</th>
  </tr>
  <tr>
    <td><img src="docs/images/light.png" alt="Whisper Desk private offline speech-to-text app in light mode, showing a completed transcript and Copy text button" width="360"></td>
    <td><img src="docs/images/dark.png" alt="Whisper Desk live local voice transcription in dark mode, showing the Finish button, audio waveform and provisional transcript" width="360"></td>
  </tr>
</table>

Actual application screenshots with demonstration text, captured at the default window size. Appearance follows your system's light or dark mode automatically on Windows.

## Why use Whisper Desk?

- **Private local transcription.** Microphone audio and speech recognition stay on your own machine. The normal app processes audio in memory rather than saving recordings.
- **Free speech-to-text.** No subscription, paid transcription API, account or usage quota imposed by the app.
- **OpenAI Whisper quality.** Uses the Whisper `turbo` model, an optimized version of `large-v3` designed for faster inference with minimal loss of accuracy. [About OpenAI Whisper](https://github.com/openai/whisper#available-models-and-languages).
- **Transcribes as you talk.** Incremental transcription starts during recording, so work is already underway when you press Finish. Live words may be revised as more context arrives.
- **Fast on compatible NVIDIA GPUs.** Local CUDA acceleration and a model that stays warm between recordings reduce waiting. CPU fallback is available.
- **A small native desktop utility.** One main button, clear audio feedback, readable text and easy copying. Built with Python and Qt; no browser or local web server.
- **Keep your thoughts together.** New recordings append beneath earlier text. Copy includes the accumulated transcript; Clear removes it.

Use it for desktop dictation, drafting emails, capturing ideas, writing notes and turning spoken thoughts into text without a cloud service.

## Record → speak → Finish → copy

1. Launch Whisper Desk and wait for **Ready for your voice**.
2. Press **Record** and start speaking. The waveform responds to your microphone, and live text begins to appear.
3. Press **Finish**. Whisper Desk reconciles the remaining audio into the final transcript.
4. Press **Copy text** and paste it wherever you need it.

Record again to add another paragraph. Earlier text stays in the window until you press **Clear**. Transcripts are kept in memory for the current window; copy anything you want to keep before closing the app.

## Get started on Windows 11

Install **64-bit Python 3.12**, download or clone this repository, then open PowerShell in its folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -e .
.\.venv\Scripts\python -m whisper_desk
```

For fast NVIDIA GPU transcription, install **CUDA Toolkit 12** and **cuDNN 9 for CUDA 12**, with a compatible driver. See the [CUDA setup guide](docs/setup-and-development.md#cuda-on-windows) and [faster-whisper GPU requirements](https://github.com/SYSTRAN/faster-whisper#gpu). The badge in the app shows **CUDA** or **CPU**.

The first launch downloads approximately **1.6 GB** of Whisper Turbo model weights. Once the download is complete and cached, you can transcribe without an internet connection. Allow microphone access for desktop apps in Windows privacy settings.

If you already have a packaged build, launch `WhisperDesk.exe` from its complete folder. To build your own executable, follow the [Windows packaging instructions](docs/setup-and-development.md#package-for-windows). A packaged app does not require Python to be installed.

## Does it work on Mac or Linux?

| Platform | Current application status | Acceleration |
| --- | --- | --- |
| **Windows 11, x64** | Verified with real microphone capture, live transcription and a packaged executable. | NVIDIA CUDA preferred; CPU fallback. |
| **macOS, Intel or Apple Silicon** | Not tested or packaged. A source port may be possible, but there is no verified Mac release. | The current engine uses CPU or CUDA; it has no Apple Metal/MPS inference path. |
| **Linux** | Not tested or packaged. Dependency support makes it a candidate for a source port, rather than a supported release today. | The underlying runtime supports CPU and NVIDIA CUDA on supported Linux systems. |

The [CTranslate2 runtime provides Windows, macOS and Linux Python wheels](https://opennmt.net/CTranslate2/installation.html), and the app skips Windows-only shell integrations on other systems. That does **not** establish full application compatibility: microphone behaviour, desktop integration and packaging still need platform testing. Linux may also need a system [PortAudio installation](https://python-sounddevice.readthedocs.io/en/latest/installation.html).

## Common questions

**Is it really offline?** Yes, after downloading the dependencies and model. Speech recognition runs locally; your recording is not uploaded for transcription.

**Do I need an OpenAI account or API key?** No. Whisper Desk runs the OpenAI Whisper model locally through [faster-whisper](https://github.com/SYSTRAN/faster-whisper), rather than calling the OpenAI API.

**Does it support other languages?** Whisper Turbo supports multilingual speech recognition. The app detects the spoken language automatically, or you can set a language code when launching, for example `--language en`. This utility transcribes speech; it does not offer a translation workflow.

**How fast is it?** On the development RTX 4060, live text appeared in roughly two seconds, and several recordings finalized in well under a second after Finish. These are measured examples, not a guarantee for every recording or computer. See the [verification notes](docs/verification.md).

## Setup, testing and development

See the [setup and development guide](docs/setup-and-development.md) for pinned dependencies, CUDA troubleshooting, streaming architecture, automated tests, visual checks and PyInstaller packaging. The [verification notes](docs/verification.md) distinguish actual hardware runs from mocked tests and remaining manual checks.

Whisper Desk is an independent application using [OpenAI Whisper](https://github.com/openai/whisper) model weights and the [faster-whisper](https://github.com/SYSTRAN/faster-whisper) inference implementation.

---

*Requires compatible hardware. Speed and transcription accuracy vary with your computer, microphone, language and audio quality; a compatible NVIDIA GPU is recommended for fast live transcription.*
