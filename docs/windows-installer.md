# Windows installer

Whisper Desk's per-user network installer includes the PyInstaller application and downloads the pinned GPU runtime and Turbo model during setup. It installs under `%LOCALAPPDATA%\Programs\WhisperDesk`, creates a Start menu shortcut and performs actual model inference before reporting success. It neither installs a graphics driver nor modifies system `PATH`.

GPU downloads total **3,438,553,716 bytes**, including the model; CPU downloads total approximately **1.62 GB**. Extraction, staging and retained downloads require additional space. Setup uses a conservative disk-space estimate, shows progress and retains verified complete downloads. Partial files are restarted rather than resumed.

## Build

Create the Python 3.12 development environment described in [the development guide](setup-and-development.md), including the pinned packaging dependencies. Install [Inno Setup 6.7.3 or newer](https://jrsoftware.org/isdl.php). A release build must receive the semantic version and actual GitHub repository; normal releases get both from the tag workflow. For a local build, set them explicitly:

```powershell
.\.venv\Scripts\python scripts/build_installer.py --version 0.1.0 --repository Sam7/whisper-desk
# Or use a compiler installed outside the standard location:
.\.venv\Scripts\python scripts/build_installer.py --version 0.1.0 --repository Sam7/whisper-desk --iscc 'C:\Tools\Inno Setup\ISCC.exe'
```

Output: `dist/installer/WhisperDesk-0.1.0-Setup.exe` plus a `.sha256` sidecar. The app, installer and Apps & Features entry all use version `0.1.0`. The builder also collects runtime dependency, Qt, Python and Whisper licence notices. PyInstaller excludes NVIDIA SDK DLLs found on the developer machine. The installer gets its download URLs and hashes from `src/whisper_desk/assets/setup-dependencies.json`; no end-user install resolves a floating latest release.

To rebuild the installer around an already rebuilt application:

```powershell
.\.venv\Scripts\python scripts/build_installer.py --version 0.1.0 --repository Sam7/whisper-desk --skip-app-build --app-source build/release/app/WhisperDesk
```

The generated installer is unsigned unless the release maintainer adds Authenticode signing. Signing credentials are not included in the repository. Build artifacts, dependencies and downloaded model files are ignored by Git. Local building does not publish anything; tagged builds and package submissions are described in the [release guide](releases.md).

The default command uses a clean PyInstaller build, and packaging rejects an executable whose embedded project code or dependency lock differs from the current source. Finish edits before building; source changes made while PyInstaller is analysing modules can otherwise leave a stale archive even when its timestamps appear recent.

## Runtime and model ownership

- `%LOCALAPPDATA%\WhisperDesk\runtime\cuda12.9-cudnn9.10.2\bin`: NVIDIA DLLs. Licence notices are in the adjacent `licenses` directory.
- `%LOCALAPPDATA%\WhisperDesk\models\turbo\0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf`: pinned model files.
- `%LOCALAPPDATA%\WhisperDesk\setup-cache`: SHA-256-addressed verified downloads.
- `setup-probe.json`, `setup-stage.json`, `setup-verification.json`: readable setup diagnostics, including driver/GPU information and loaded DLL paths.

Directories become active only after complete file verification. A `ready.json` inventory records file sizes and hashes. Ordinary launches check completeness without hashing several gigabytes on every startup; setup/repair performs full hash verification. The installed application uses its local model directly and does not silently download another copy. Run Setup again to repair missing/damaged files.

Installed GPU mode sets `CUDA_PATH` **inside the process** to the app-owned runtime root: CTranslate2 explicitly uses that variable for its cuBLAS loader. CPU installation records `gpu_enabled: false`; ordinary launches respect that choice, while an explicit `--device cuda` remains a diagnostic override. Source launches retain their original external CUDA discovery.

NVIDIA's driver remains an operating-system prerequisite. Setup probes the driver, then performs real encoder/decoder inference; a driver detection result alone is not treated as GPU success. GPU verification rejects CPU fallback and DLLs loaded outside the owned runtime. A bad GPU check lets the user retry after updating the driver or go back and select slower CPU mode.

Uninstallation retains downloaded models, runtimes, setup cache and logs by default. Interactive uninstall offers to remove them explicitly. Silent uninstall retains them. Copy any transcript you want to keep before closing an app for an upgrade; transcripts remain in memory.

## Verification and smoke tests

```powershell
.\.venv\Scripts\python -m pytest -q
# Download/stage isolated developer test data (uses the exact locked files):
.\.venv\Scripts\python scripts/setup_dependencies.py --root artifacts/setup-smoke --cache artifacts/setup-cache --stage-only
# Use the packaged app for isolation checks: the source CTranslate2 wheel itself contains a cuDNN DLL.
.\dist\WhisperDesk\WhisperDesk.exe --setup-verify --setup-root "$PWD\artifacts\setup-smoke" --setup-output "$PWD\artifacts\setup-smoke\verification.json" --require-cuda --setup-audio "$PWD\tests\data\jfk.flac"
.\.venv\Scripts\python scripts/audit_runtime.py --runtime artifacts/setup-smoke/runtime/cuda12.9-cudnn9.10.2/bin --app dist/WhisperDesk --output artifacts/setup-smoke/runtime-audit.json --verify-cudnn
```

Hidden setup commands are `--setup-probe`, `--setup-stage` and `--setup-verify`. Each writes JSON to `--setup-output`; probe exits 0 for a CUDA driver, 10 without NVIDIA hardware and 11 for NVIDIA hardware with an unavailable driver. Stage/verification exit 1 on failure. `--require-cuda` requires actual GPU inference. `--setup-root` isolates smoke-test data; normal installation uses the per-user data directory. Windows GUI executables should be invoked with `Start-Process -Wait` when a shell needs to wait for their exit.

For automated installer runs, use `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /LOG=...`; add `/CPU=1` to explicitly exercise CPU installation. Use an isolated account for fresh-install testing. Installer logs and the JSON diagnostic reports must agree before declaring success.

For an interactive install with automatic wizard navigation and progress screenshots, run `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/smoke_install.ps1 -Install`. This performs real installation in the current account; use the capture-only script above when installation is not wanted.

1. On clean Windows 11 x64 with an NVIDIA driver **but no Python, CUDA Toolkit, cuDNN or model cache**, install GPU mode. Verify the actual loaded CUDA/cuDNN DLLs come from the app-owned directory.
2. Disconnect the network after setup. Launch from the Start menu; exercise microphone → live text → Finish → edit → Copy, and a second appended recording.
3. Repeat on a CPU-only machine. Check no GPU downloads occur, the badge shows CPU, and transcription works.
4. Test download interruption, Retry/Cancel, checksum failure, low disk space and an unavailable/old driver. Cancel during staging must not leave an active partial model.
5. Test upgrade with cached dependencies, a path containing spaces, an ordinary non-admin account, and uninstall both retaining and explicitly removing downloads.
6. Inspect screenshots of the wizard, acceleration choice, download progress and error/verification states. Inspect the installed application in light and dark mode.

The wizard's initial, acceleration and ready pages can be captured without installing:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/capture_installer.ps1 -Theme light -Output artifacts/installer-ui/light
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/capture_installer.ps1 -Theme dark -Output artifacts/installer-ui/dark
```

The capture script temporarily selects the requested Windows app appearance and restores the original value in `finally`. It captures only the installer window and cancels before clicking Install.

The development machine has CUDA installed. Clearing environment variables and auditing loaded DLL paths is useful isolation evidence, but does not replace the clean-machine GPU test. Record remaining hardware/environment limits in [verification notes](verification.md).

## Updating dependency pins

`scripts/lock_setup_dependencies.py` is an explicit maintainer tool. It regenerates checksums/URLs from NVIDIA's CUDA 12.9.1/cuDNN 9.10.2 manifests and the fixed Turbo revision. Changing GPU versions also requires a new runtime directory identifier, reviewing licence/driver compatibility, rerunning the DLL import audit and repeating the clean-machine inference tests. Never run lock regeneration during installation.
