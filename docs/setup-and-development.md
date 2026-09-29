# Whisper Desk — setup and development

A small Windows 11 utility: **Record → speak → Finish → copy → paste**. Python 3.12, native PySide6, local Whisper Turbo, and low-latency WASAPI capture. No browser or server.

![Whisper Desk](images/light.png)

![Whisper Desk recording in dark mode](images/dark.png)

## Run on this machine

The environment and packaged build were created during development:

```powershell
.\.venv\Scripts\python -m whisper_desk
# Or double-click dist\WhisperDesk\WhisperDesk.exe
```

Wait for “Ready for your voice” on the first launch. Record starts capture immediately; live text is provisional. Finish ends recording and reconciles the remaining audio. Each recording appends a new paragraph beneath earlier text. Revisions affect only the current recording; previous results and visible partial text from a failed recording are preserved. Copy text copies everything; Clear removes it all. A silent recording preserves earlier text too. Text is retained in the current window, not saved between application launches. You can also select and copy part of the text. The microphone follows the Windows default input device at startup. Change that in Windows Sound settings and restart the app.

Appearance follows Windows automatically, including changes while recording. The violet microphone becomes a rose Finish control. The larger audio bars overlap the fading edge of the button halo and respond to quiet speech too. The hand cursor and hover illumination use exactly the circular click target. Idle has no continuous animation. Windows' animation preference is respected and animation timers pause when hidden or minimized. The native titlebar and custom taskbar icon remain. There is no theme selector or bottom slogan.

The default client area is 540 × 770 logical pixels, with a 440 × 560 minimum. At narrow widths the backend badge moves below the subtitle. Inline error/CPU notices reclaim some space from the microphone control so the transcript remains usable. `theme.py` owns palettes/platform appearance and `ui_components.py` owns vector painting; transcription workers have no theme dependencies.

## Fresh environment

The transcript is editable whenever the app is not recording or finalizing. Plain-text typing/paste, deletion and undo/redo update Copy/Clear and the empty state immediately. Starting a new recording snapshots the edited text; live revisions affect only the new tail. Editing is locked while that tail is being generated, so keyboard input cannot be silently overwritten by Whisper.

Install 64-bit Python **3.12** and run from the repository directory:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements-lock.txt
.\.venv\Scripts\python -m pip install -e '.[dev]'
.\.venv\Scripts\python -m whisper_desk
```

`pyproject.toml` defines the dependency ranges; `requirements-lock.txt` pins the versions used for verification on Windows. The lock includes development/packaging tools. For runtime dependencies alone, use `pip install -e .` instead of the last two install commands.

The first launch downloads approximately 1.6 GB of Turbo model weights to the standard Hugging Face cache (`%USERPROFILE%\.cache\huggingface\hub`). Subsequent launches resolve the local cache first and work offline. Allow additional disk space for the Python environment, model, and packaging. Model loading and warm-up happen once at startup, in the background. A failed first download produces a concise message; restart after restoring connectivity.

Audio is processed in memory and never saved by the normal app. Transcription runs locally. Debug logs contain timings and exception details, not transcripts. Development speech exercises explicitly write their test transcripts to their output folder.

## CUDA on Windows

Use a current NVIDIA driver, **CUDA Toolkit 12**, and **cuDNN 9 for CUDA 12**. A driver's advertised CUDA version alone does not install these inference libraries. These requirements come from [faster-whisper's GPU documentation](https://github.com/SYSTRAN/faster-whisper#gpu).

- [CUDA Toolkit installation for Windows](https://docs.nvidia.com/cuda/cuda-installation-guide-microsoft-windows/)
- [cuDNN installation](https://docs.nvidia.com/deeplearning/cudnn/installation/latest/windows.html)

The app discovers `CUDA_PATH\bin` and NVIDIA's official `C:\Program Files\NVIDIA\CUDNN\v9*\bin\12*` installations. Custom DLL locations can be added to `PATH` or supplied with:

```powershell
$env:WHISPER_CUDA_PATH = 'C:\your\cuda-runtime\bin'
.\.venv\Scripts\python -m whisper_desk
```

CUDA uses `float16`; CPU uses `int8`. The UI badge shows the actual backend. A CUDA load or warm-up failure falls back to CPU and logs the reason. CPU is usable but substantially slower. To force CPU, or avoid repeated language detection by selecting English:

```powershell
.\.venv\Scripts\python -m whisper_desk --device cpu
.\.venv\Scripts\python -m whisper_desk --language en
```

If CUDA inference fails after successful warm-up, the app preserves the visible text and allows another recording. It does not silently switch models or discard quality to hide a failure.

Windows Settings → Privacy & security → Microphone must allow microphone access **and desktop apps**. No microphone selector or settings panel is needed for the basic workflow.

## How streaming works

- An audio owner prepares the WASAPI stream at startup, then starts/stops it independently of inference. Capture uses 20 ms mono float32 blocks at 16 kHz; WASAPI shared-mode conversion handles the device's native rate.
- A separate inference owner holds one warm Turbo model and runs serial decoding. The UI receives queued Qt signals; it never opens an audio device or calls Whisper.
- First live decoding begins at 1.5 seconds of captured audio. Further passes start roughly every second. Slow passes consume the latest buffer rather than building a queue of obsolete inference jobs.
- Completed sentences outside a five-second mutable tail can be committed. Two seconds of overlap preserve context. Text matching in the overlap handles moving Whisper timestamps; time alone cannot safely deduplicate words.
- A 24-second maximum inference window forces progress even without punctuation. Consumed audio is pruned. A 120-second unprocessed backlog produces a recoverable error instead of unlimited memory growth.
- Stop ends capture promptly on its own thread. An in-flight decode completes, then the remaining tail is reconciled. If only confirmed silence arrived after the last complete live decode, its result is reused. Earlier committed sentences are retained; recordings are not reprocessed in full at Stop.

Short recordings can remain entirely provisional until Stop. Longer recordings commit work before Stop. This is incremental Whisper decoding, not a model with native token streaming. Both live and final decoding use beam size 3; live uses deterministic temperature and final allows one bounded retry. This preserved accuracy better than greedy decoding in the actual streaming tests. Batching is unnecessary for one short interactive stream.

Code is deliberately small: `app.py` bootstraps, `ui.py` owns Qt, `audio.py` owns capture/buffering, `engine.py` owns Whisper, `transcript.py` reconciles text, and `session.py` coordinates the two background owners. Audio/model boundaries are injectable. Window close requests cancellation and closes audio; an already-running native inference call cannot be interrupted mid-kernel, but its result is suppressed. The process does not wait indefinitely for it.

## Tests and visual verification

```powershell
# Hardware-free tests, including Qt controls
.\.venv\Scripts\python -m pytest -q

# Full suite, including a real Turbo transcription of known speech
$env:WHISPER_INTEGRATION = '1'
.\.venv\Scripts\python -m pytest -q
Remove-Item Env:\WHISPER_INTEGRATION

# Render empty, recording, result, short/long, loading, finishing,
# error, hover and pressed states without opening the microphone
.\.venv\Scripts\python scripts\capture_ui.py

# Actual Windows light/dark switching and native titlebar checks.
# Temporarily changes the app appearance setting and restores it on exit.
.\.venv\Scripts\python scripts\verify_windows_theme.py
.\.venv\Scripts\python scripts\verify_pointer.py

# Headless DPI rendering, using installed Segoe UI fonts
$env:QT_QPA_PLATFORM = 'offscreen'
try {
    foreach ($scale in @('1', '1.25', '1.5', '2')) {
        $env:QT_SCALE_FACTOR = $scale
        .\.venv\Scripts\python scripts\capture_ui.py --output "artifacts/dpi-$scale"
    }
} finally {
    Remove-Item Env:\QT_QPA_PLATFORM
    Remove-Item Env:\QT_SCALE_FACTOR
}

# Real CUDA + real-time known speech + actual Qt buttons/clipboard
# Leave the test window open; it closes itself.
.\.venv\Scripts\python scripts\exercise_app.py
.\.venv\Scripts\python scripts\exercise_app.py --theme dark --output artifacts\exercise-dark
.\.venv\Scripts\python scripts\exercise_app.py --sessions 2 --output artifacts\append-live
.\.venv\Scripts\python scripts\exercise_app.py --repeat 3 --output artifacts\long-session

# Six seconds of real microphone capture, with live/final inference
.\.venv\Scripts\python scripts\exercise_app.py --microphone --output artifacts\microphone
```

The known speech fixture and its provenance are in `tests/data/README.md`. The exercise requires every expected phrase once per repetition, live text before Stop, and correct Copy/Clear behavior. It records JSON results, latency logs, screenshots, and GUI heartbeat timing. Automated tests cover transitions, rapid clicks, repeated sessions, transcript revisions, timestamp drift, long backlog draining, microphone interruption, model/CUDA errors, cancellation and shutdown.

The capture script writes `artifacts/ui-redesign/light` and `artifacts/ui-redesign/dark`; each contains 19 representative states, including silence, focus, copy confirmation and accumulated transcripts. `geometry.json` records logical sizes and device scale. The latest interaction follow-up captures are in `artifacts/interaction-update`. Real workflow screenshots are in each exercise output directory. Generated artifacts are ignored by Git. [Development verification notes](verification.md) record observed outcomes and limitations. Headless DPI captures verify rendering at fixed scales; physical monitor-to-monitor transitions remain a manual check.

Manual smoke test:

1. Launch; verify CUDA • TURBO and wait for Ready.
2. Record and immediately say: “The meeting starts at nine tomorrow morning. Please bring the blue notebook.” Check the level meter and live words; Finish and compare the final text.
3. Copy and paste into Notepad. Record again without clearing; confirm it adds a new paragraph. Repeat three recordings, including one finished mid-sentence. Confirm the model does not reload, then Clear.
4. Press Record/Finish rapidly. Resize to the minimum and enlarge it; try a long transcript and scroll through it. Move across the circular button edge; hand cursor, hover glow and clickability must agree.
5. Unplug the microphone while recording; reconnect and retry. Test microphone access disabled in Windows, then restore it.
6. Close during recording, and again while finishing. Confirm there is no hanging process or microphone indicator.
7. Check CPU operation with `--device cpu`. The badge must say CPU; latency will be longer.
8. Change Windows Settings → Personalization → Colors → app mode while recording and finishing. Confirm text selection, scrolling, focus and controls survive. Check Windows Animation effects off, and move between differently scaled monitors.

The development run exercised the real microphone, CUDA, known speech, repeated speech, clipboard, screenshots, error mocks and shutdown. Physical hot-unplug, privacy toggling, and an all-day soak are still manual checks; automated mocks are not evidence of physical device behavior.

## Timings

Logs: `%LOCALAPPDATA%\WhisperDesk\logs\app.log` (rotated). Source launches also print to the console. Timings distinguish first actual audio callback, first visible transcript, incremental inference duration/backlog, model warm-up and Stop-to-final.

On the development RTX 4060 8 GB / PD200X WASAPI input, observed capture latency was **42–47 ms**. A 33-second known speech exercise showed first text in **2.2 s** and Stop-to-final in **582 ms**; a six-second real microphone exercise finalized in **346 ms**. A test with confirmed trailing silence reused the live result in **32 ms**. These are observations, not guarantees. First text includes the initial 1.5-second audio context; Stop during an in-flight decode may wait for that decode plus final reconciliation.

## Package for Windows

```powershell
.\.venv\Scripts\python -m PyInstaller --noconfirm whisper-desk.spec
.\dist\WhisperDesk\WhisperDesk.exe
```

Distribute the **whole `dist\WhisperDesk` folder**, not just the executable. The folder build avoids one-file extraction on every launch. Python need not be installed on the destination PC. CUDA/cuDNN must be installed separately there; the model downloads on first launch or can be pre-populated in the Hugging Face cache. Models and NVIDIA's runtime are deliberately not bundled.

The executable embeds the purple microphone icon at 16–256 px, and the app sets the Windows identity `WhisperDesk.Desktop` before creating its UI. To replace an older Python-logo taskbar entry, unpin it, launch `dist\WhisperDesk\WhisperDesk.exe`, and pin that app again. Pin the packaged executable for normal use. Regenerate the shared icon with `scripts/generate_icon.py`; verify the actual EXE's shell icons with `scripts/verify_shell_icon.py` after rebuilding.

To verify the packaged executable against known speech (opens and closes a test window):

```powershell
.\dist\WhisperDesk\WhisperDesk.exe --verify-audio "$PWD\tests\data\jfk.flac" --verify-output "$PWD\artifacts\packaged"
```

The hidden verification option runs the same repeatable Qt/CUDA exercise as the source script. Inspect `report.json` for errors and `timings.log` for timings. This is development tooling, not an additional product UI.

Add `--verify-sessions 2` to exercise two recordings with accumulated text and one warm model; add `--verify-theme light` or `--verify-theme dark` for deterministic appearance checks.
