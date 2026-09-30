# Verification — 28–29 September 2026

Default-height follow-up: increased the starting client height from 620 to 770 logical pixels, retaining width 540 and the existing minimum. The additional 150 pixels expand the transcript card. Updated the capture harness and README dimensions; 16 focused UI/theme/history checks passed. Rendered and inspected the taller default layout in both themes (`artifacts/taller-default`) and refreshed the curated documentation screenshots.

## Appearance redesign — 29 September

Implemented the approved compact light/dark reference design: large centered brand, native Windows frame, layered violet microphone control, rose recording state, responsive badge, quiet level meter, rounded transcript card, vector action icons and copy confirmation. Removed the bottom slogan and its reserved space. CPU/error notices now appear between the audio caption and transcript. Production follows Windows automatically; forced themes exist only in diagnostic tooling.

Source and packaged controls were exercised with real CUDA inference. The source suite passed **48 tests**, including the real Turbo fixture. Nine new tests cover theme resolution, queued appearance updates, state/selection/scroll/focus preservation, circle hit testing, keyboard Stop, disabled finishing, compact notices, empty/final status, copy feedback and animation lifecycle. Existing recording and orchestration tests remain intact.

| Redesign exercise | Observed result | Evidence |
| --- | --- | --- |
| Windows light → dark while recording | Qt appearance and native titlebar updated; selected text and Stop state survived; original Windows setting restored | `artifacts/windows-theme/report.json`, native frame screenshots; `scripts/verify_windows_theme.py` |
| Source, known speech, dark | All expected phrases, live text before Stop, clipboard/Clear; first text 2630 ms; Stop→final 793 ms | `artifacts/redesign-live-dark/report.json` |
| Source, known speech, light | Same accuracy/control checks; first text 2495 ms; Stop→final 770 ms | `artifacts/redesign-live-light/report.json` |
| Physical WASAPI input, dark | First audio callback 33 ms; live and final words; first visible text 2520 ms; Stop→final 568 ms; clipboard/Clear | `artifacts/redesign-microphone/report.json`, `timings.log` |
| First redesigned EXE, known speech, dark | CUDA; all expected phrases; first text 2184 ms; Stop→final 747 ms; max heartbeat gap 139 ms; exit 0 | `artifacts/redesign-packaged-dark/report.json`, screenshots |
| Final rebuilt EXE, known speech, light | CUDA; all expected phrases; first text 2621 ms; Stop→final 507 ms; max heartbeat gap 238 ms; clipboard/Clear; exit 0 | `artifacts/redesign-packaged-final/report.json`, screenshots |

These runs overlapped dependency scanning/rendering during development. They prove the workflow and remain individual observations rather than clean performance benchmarks. Model warm-up in the busy source runs took 8–13 seconds. The physical microphone speech had no controlled script, so its text does not establish an accuracy score.

Rendered 17 states per theme at the native display scale and at fixed 100%, 125%, 150% and 200% scales. Actually opened representative empty/recording/result, narrow/long/error, loading, focus and copied PNGs. The default card has a 72-logical-pixel text viewport; the narrow empty card has 54 pixels, sufficient for its 40-pixel hint. Long content scrolls rather than expanding the window. High-DPI headless captures explicitly load Windows Segoe UI because the offscreen Qt platform cannot discover system fonts automatically; they do not verify moving between physical monitors.

Visual inspection caught and corrected a generic Qt style overriding the large heading, insufficient status-dot spacing, an overly flat halo, and disabled Copy resembling an outlined secondary action. A copy-confirmation timer also retained the check icon after resetting its label; that is corrected. Native frame captures use Windows PrintWindow to capture only this app, including the titlebar, even when another window is foreground. Curated screenshots are retained in `docs/images`; the complete repeatable captures are under `artifacts/ui-redesign` and `artifacts/dpi-*`.

The rebuilt EXE retains the stable app identity and purple microphone icon. Windows shell extraction returned nonempty custom 32/16 px icons, which were visually inspected. The native light/dark frame captures also show the custom titlebar icon. Windows may retain an older pinned Python shortcut until it is unpinned and replaced with the packaged executable.

Reopened the final normal application and confirmed CUDA warm-up and the ready state in its log and actual native window capture (`artifacts/redesign-running.png`). Its live `WM_GETICON` image was also captured and visually inspected. Compared the embedded executable's Python code objects with current source for application, UI, painted components, theme and diagnostics; all five matched.

Remaining manual checks: physical monitor-to-monitor DPI changes, physical microphone hot-unplug/privacy toggling, and an all-day soak. Appearance changes during finishing are covered by Qt tests; the live Windows setting smoke test used the recording state.

Environment: Windows 11 build 26200, Python 3.12.3, PySide6 6.11.2, faster-whisper 1.2.1, CTranslate2 4.8.2, RTX 4060 8 GB. CUDA Toolkit 12.9 and cuDNN 9.9 were already installed. The existing local Turbo cache was used.

## Interaction and transcript preservation follow-up — 29 September

The primary face now uses the same circular test for mouse cursor, hover illumination and clicks. The decorative rectangular canvas and halo show an arrow. Disabled loading/finishing controls show an arrow too. Actual Windows pointer movement verified both inside and outside the face at 540- and 440-pixel window widths (`scripts/verify_pointer.py`); deterministic Qt mouse-event tests also cover the circular edge and rectangular corner.

Lowered the microphone/finish symbols by eight logical pixels and renamed the active action **Finish**. Bars are five pixels wide rather than three, with up to 54 pixels of height in the standard layout. Quiet speech uses a nonlinear amplitude mapping. The waveform overlaps the last 20 pixels of the fading halo, with mouse events passing through, to preserve transcript space. The narrow layout uses a 40-pixel meter. Actual screenshot review found that allocating all the added bar height below the circle cramped the error transcript; the overlapping layout corrected this. Empty, recording, error and accumulated-text captures were inspected in both themes; 200% rendering is repeatable too.

Starting a recording snapshots the existing visible transcript as an immutable prefix. Whisper's live and final revisions replace only the current recording's tail, separated from earlier recordings by a blank paragraph. Retry preserves visible partial words from a failed recording, and a silent recording preserves all earlier text. New recording starts follow the bottom; finalization no longer jumps back to the beginning. Copy returns the complete accumulated transcript. Clear resets both the visible text and the stored prefix, preventing old text reappearing later. History is in memory for the current window, not persisted to disk.

The complete suite passed **54 tests**, including real Turbo inference. New tests cover cursor/hover boundaries at both widths, append/revision semantics, silent recordings, failed recordings and retry, Clear, bottom scrolling and two recordings through the actual Qt event bridge with a warm mock model. Hardware-free suite: 53 passed, 1 integration test skipped. A real CUDA exercise recorded the known speech twice, checked all phrases once per recording, verified the old paragraph remained on Record, copied both paragraphs and cleared them. Source first-text times were 2147/2122 ms and Finish-to-final times 420/453 ms; max GUI heartbeat gap 111 ms (`artifacts/append-live/report.json`). One model warm-up was logged across both recordings.

Windows light/dark switching was rerun successfully with the Finish state and larger waveform. Source screenshots contain 19 states per theme, including append-in-progress and accumulated results. The rebuilt executable's embedded code was compared with current source for app, UI, painted controls, theme and diagnostics; all matched. Packaging retained the custom icon and Windows identity.

The final packaged two-recording CUDA exercise also passed: both full known-speech paragraphs remained in order, every expected phrase occurred twice, the clipboard matched the combined text, and Clear emptied the window. Exit code 0; no reported errors (`artifacts/append-packaged/report.json`). Inspected its actual rendered result and the 200% append-in-progress capture. One model initialization served both recordings. The normal updated executable was reopened afterward.

## Observed runs

| Exercise | Result | Evidence |
| --- | --- | --- |
| Real Turbo, 11-second JFK fixture | Correct known phrases; CUDA inference 834 ms in the first direct run | `tests/test_integration.py`; console execution |
| Original microphone path | 590 ms to first capture callback | Console hardware probe |
| Prepared WASAPI path | 42 ms to first capture callback | Console hardware probe |
| Revised 11-second streaming run | All known words preserved; Stop→final 447 ms | `artifacts/exercise-v2/report.json` |
| Final 33-second streaming run | All three expected phrase sets preserved; first text 2234 ms; Stop→final 582 ms; maximum GUI heartbeat gap 110 ms | `artifacts/long-session-v3/report.json`, `timings.log`, screenshots |
| Six-second real microphone run | Live and final speech appeared; capture 47 ms; Stop→final 346 ms; Copy and Clear verified | `artifacts/microphone-v2/report.json`, `timings.log`, screenshots |
| Final source 11-second streaming run | Complete known speech; first text 2192 ms; Stop→final 465 ms; max heartbeat gap 86 ms | `artifacts/final-source/report.json` |
| Real CPU fallback backend | Correct known speech; model warm-up 12.4 seconds; 11-second sample inference 18.1 seconds | Console hardware probe with `Config(device='cpu')` |
| Real speech with 1.2-second trailing silence | All known phrases preserved; silence-only final result reuse; Stop→final 32 ms in Qt (22 ms in service log) | `artifacts/silence-tail/report.json`, `timings.log` |
| Final PyInstaller executable | CUDA; all known phrases preserved; first text 2130 ms; Stop→final 420 ms; max heartbeat gap 96 ms; Copy/Clear verified; exit code 0 | `artifacts/packaged-final/report.json`, `timings.log`, screenshots |

The actual microphone text was “GDP went up fourfold. Real manufacturing went up six times.” Its speech content had no controlled reference, so this proves capture/inference/UI integration, not a measured accuracy score.

The long speech fixture was delivered in real time at 16 kHz/20 ms blocks through the injected audio boundary, while using the actual model, Qt buttons, event bridge, clipboard and renderer. That test is distinct from the separate physical microphone test.

The latest complete test suite passed **39 tests**, including real Turbo inference (`WHISPER_INTEGRATION=1`). CUDA fallback selection and missing-library handling are also tested with mocks; CPU inference itself was separately exercised on the real machine.

## Problems found and corrected

- Empty placeholder text was visibly clipped in the first screenshots. Replaced it with a properly sized empty-state label.
- Disabled Copy/Clear initially resembled enabled controls. Added explicit disabled styles.
- Final long text opened at a partially clipped line because live scrolling followed the bottom. Final results now open at the beginning; live updates still follow the bottom unless the reader has scrolled away.
- Default microphone startup took ~590 ms. Prefer WASAPI with shared-mode rate conversion and prepare the stream once before recording; measured ~42–47 ms afterward.
- Timestamp-only overlap reconciliation dropped words when Whisper moved timestamps. Reconcile a committed text suffix in the overlap and retain uncommitted context.
- Greedy word-by-word commitment lost sentence context in the 33-second fixture. Use beam size 3, sentence-boundary commitment and a five-second mutable tail. The same accuracy assertions subsequently passed for all three repetitions.
- Long synthetic backlog testing exposed pruning that only removed whole callback blocks. Pruning now releases prefixes inside a block too. Oversized first blocks are also rejected.
- A UI automation race could click Record before the queued Ready state reached Qt. The exercise now waits for the window's displayed state and treats premature window closure as an interrupted test.

## Visual QA

Rendered Qt captures were actually opened and inspected for empty, recording, final result, short text, long text at minimum width, loading, finishing and error states. Hover and pressed states are also reproducible. Check `artifacts/ui/` and the actual workflow folders. No browser approximation was used.

The inspection checked spacing, button hierarchy, disabled controls, input feedback, typography, wrapping, clipping and scrolling. The empty-state and final-scroll fixes were made after inspecting screenshots, not inferred from source code.

## Limits

Taskbar icon follow-up: added a shared multi-resolution purple microphone ICO, embedded it into the PyInstaller executable, and set the stable Windows AppUserModelID before UI creation. Rebuilt and relaunched successfully on CUDA. Hardware-free suite: 38 passed, real-inference test skipped for this cosmetic change. Windows `ExtractIconExW` returned the custom large/small executable icons (40/20 px at current DPI), and `WM_GETICON` returned the same custom icon from the running window. All three extracted images were visually inspected in `artifacts/shell-icon`. Older pinned entries may need unpinning and repinning from the rebuilt executable.

Hardware-free tests verify unavailable microphones, interrupted callbacks, disconnection, CUDA fallback, model errors and lifecycle failures with injected boundaries. Actual physical hot-unplug, Windows privacy toggles, missing CUDA DLLs on a clean PC, multi-monitor DPI transitions and an all-day soak still require the README manual procedure. Background native CUDA calls cannot be cancelled mid-kernel; their late results are suppressed on shutdown.

Timings are individual development observations, not statistical latency guarantees. CPU throughput and language choice differ. The overlapping strategy intentionally allows provisional text to change and can still inherit Whisper's recognition errors.

## Editable transcript follow-up

The transcript accepts plain-text typing, paste, deletion, undo and redo after Finish. Copy uses the edited text, and the next recording preserves those corrections. Editing is temporarily locked during capture and finalization so live Whisper revisions cannot overwrite a concurrent edit.

Hardware-free suite: **55 passed, 1 real-inference test skipped**. Tests exercise editing, undo/redo, deletion to the empty state, Copy, preserving corrections across recordings and locking input while busy. Light and dark edited-state screenshots were rendered and visually inspected in `artifacts/editable-ui/`.

The rebuilt executable was launched and its actual Windows transcript field accepted an edit through UI Automation. The existing application was then closed cleanly, replaced and reopened; its 215-character transcript was restored and read back exactly, without changing the clipboard.

## Automatic Windows installation — 29 September

The complete suite passed **77 tests**, including real Whisper Turbo inference (`WHISPER_INTEGRATION=1`). The hardware-free run passed 76 tests with that integration test skipped. Added coverage exercises the locked manifest, verified downloads and cache reuse, damaged files, safe archive extraction, atomic replacement, cancellation, CPU installation preference, strict GPU verification, repair feedback and setup JSON failure reports.

The actual Inno Setup installer was built, installed, upgraded, uninstalled and reinstalled on the development Windows 11 machine. The first installation began with an empty app-owned download cache, model directory and runtime directory. Setup downloaded all **3,438,553,716 bytes** from the locked official sources, checked hashes, staged the files and ran real CUDA encoder/decoder inference before and after installing the application. Installation completed in **389.5 seconds**, with a working Start menu shortcut and uninstaller. Evidence: `artifacts/installer-smoke/report.json`, progress screenshots and `install.log`.

Upgrade and reinstall succeeded using verified cached downloads; neither log contains a new download transfer. Silent uninstall removed the executable and retained the model, GPU runtime and download cache as intended. Evidence: `artifacts/installer-upgrade.log`, `installer-uninstall.log` and `installer-reinstall.log`. The interactive option to delete all retained data has not been exercised on this profile, which contains existing user logs.

The installed application completed two real-time known-speech recordings with an outbound Windows Firewall block applying specifically to its executable. It used the app-owned Turbo model and CUDA libraries, preserved both paragraphs, verified Copy/Clear and reported no errors. The dark-mode run observed first text in **2115 ms**, Finish-to-final in **405 ms** and a maximum GUI heartbeat gap of **96 ms**. This exercises actual Qt controls, rendering and inference with injected known audio; it does not replace a physical microphone test. Evidence: `artifacts/installed-offline-dark/report.json`, screenshots and timing logs. The temporary firewall rule was removed and the original clipboard restored afterward.

Separately, packaged CPU inference used an isolated model-only installation with no owned GPU runtime, produced the expected known phrases and loaded no NVIDIA runtime modules. CPU model initialization took approximately 23 seconds; setup verification including the sample took approximately 56 seconds. Evidence: `artifacts/cpu-smoke/verification.json`.

The native dependency audit resolved the static and delay-loaded imports of all **16 x64 runtime DLLs**. A separate native CUDA/cuDNN exercise selected the GPU and successfully created and destroyed a cuDNN 9.10.2 handle, with all loaded runtime DLLs coming from the owned directory. Whisper inference on the pinned CTranslate2 version loaded cuBLAS and cuBLASLt; the cuDNN handle exercise verifies cuDNN separately. Evidence: `artifacts/setup-smoke/runtime-audit.json` and `runtime-audit-cudnn.json`.

Rendered light/dark wizard screenshots were captured and inspected, including initial, acceleration and ready pages, plus actual model/library downloads, staging, installed-app verification and completion. They show readable native Windows controls without clipped labels or exposed download hashes. Evidence: `artifacts/installer-ui/` and `artifacts/installer-smoke/`. Installed-app empty, recording and accumulated-result screenshots were inspected in both themes. The light-mode offline two-recording run also passed: first text **2124 ms**, Finish-to-final **437 ms**, maximum GUI heartbeat gap **96 ms**, no errors (`artifacts/installed-offline-light/`).

Two packaging issues were found and corrected: CTranslate2's cuBLAS loader uses `CUDA_PATH` directly, so installed processes now point it at the owned runtime as well as isolating `PATH`; incidental NVIDIA DLLs from the build machine are excluded. A stale PyInstaller archive was also detected by comparing compiled modules against current source. The builder now uses a clean build and rejects mismatched project code or dependency locks. The final executable's embedded project code and manifest were verified against the repository.

After validation, the existing taskbar launch folder was replaced with the verified clean build, retaining the prior build as a local backup. The installed app was opened normally, its editable transcript field was restored from the previous window in memory and checked for an exact match, and its window state was preserved. The clipboard was not changed by that replacement.

**Release validation still required:** this machine already has a CUDA Toolkit installed. Owned DLL-path checks and native import audits are useful isolation evidence, but a clean Windows 11 machine with only an NVIDIA driver remains a release gate. Physical CPU-only hardware, an ordinary non-admin account, explicit removal of retained data, low-space installation and real driver failure scenarios also remain manual checks. Setup is per-user and its logs confirm non-administrative install mode, but that is not a separate standard-account test. Windows Sandbox is unavailable here. The installer is unsigned, built locally and has not been published as a release.

## Tagged release pipeline — 30 September

The tag-driven release implementation passes the hardware-free suite (**94 passed, 1 skipped**) and a separate real Whisper Turbo known-speech integration test (**1 passed**). A local `v0.2.3` production build completed through PyInstaller and Inno Setup; the executable reported `WhisperDesk 0.2.3`, and the 110,922,266-byte installer was named `WhisperDesk-0.2.3-Setup.exe` with SHA-256 `df4f4727e995fcb3eb8f383734fe415ce09fa1fb91334fa459c877413856969d`. The version and immutable URLs in its release metadata use the configured `Sam7/whisper-desk` repository and `DotSam` publisher.

`choco pack` generated a real `whisperdesk.0.2.3.nupkg`; the package verifier confirmed version, publisher, installer URL, checksum and silent install/uninstall arguments. The three initial WinGet manifests were generated for `DotSam.WhisperDesk` and their version, URL, hash, product code and Apps & Features values were inspected. The Chocolatey public feed returned no exact `whisperdesk` package from a read-only search at validation time; actual ownership and publication still require the publisher account.

The release YAML parses and its tag trigger and per-job GitHub permissions were checked. The real unattended installer install/inference/uninstall test and Chocolatey install/uninstall smoke test are included in the Windows tag workflow. They were not run in this developer account because they install over and remove the existing per-user WhisperDesk installation; the release builder itself used an isolated `build/release` directory. No release tag was created, and no public GitHub, Chocolatey or WinGet submission was made. Configure the two documented Actions secrets before creating the first release. Clean-machine GPU validation remains outstanding as described above.
