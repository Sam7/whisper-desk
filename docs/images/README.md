# README screenshots

These PNGs are repository assets, intentionally outside the ignored `artifacts/` directory. Commit them with the root README so the images render on GitHub and in a fresh clone.

- `light.png`: light appearance, completed transcription.
- `dark.png`: dark appearance, live recording and provisional transcription.

Captured and visually inspected on Windows on 29 September 2026, at the application's 540 × 770 logical-pixel default. These are actual Qt widget renders using demonstration text and deterministic audio levels; they are not screenshots of a controlled live microphone accuracy test.

From the repository root, regenerate with:

```powershell
.\.venv\Scripts\python scripts\capture_ui.py --output artifacts\readme-captures
Copy-Item artifacts\readme-captures\light\result.png docs\images\light.png
Copy-Item artifacts\readme-captures\dark\recording.png docs\images\dark.png
```

Open and inspect both PNGs before updating them. The complete capture harness renders additional states for visual QA; only these two curated screenshots belong in the public README.
