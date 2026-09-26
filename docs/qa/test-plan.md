# Test Plan

## Automated (CI, every push/PR)
Scope: `tests/unit`, `tests/integration`, `tests/e2e`, `ruff`, `mypy`,
`gitleaks`, `pip-audit`. See `docs/qa/test-strategy.md` for what each
level covers, and `docs/qa/test-cases.md` for the catalogue.

**Entry criteria**: code compiles, `pip install -e .[dev,captions]`
succeeds.
**Exit criteria**: all CI jobs green (`lint`, `gitleaks`, `test` on both
OSes; `dependency-audit` is informational and doesn't gate).

## Manual real-engine verification (GPU hardware required)

Not automatable on hosted CI runners (no GPU — ADR-0007). Performed by
the maintainer on the reference machine (RTX 5070 Laptop, 8 GB VRAM,
Windows 11, Python 3.14) before each release that touches a heavy stage.

| # | Scenario | Steps | Expected result | Last verified |
|---|---|---|---|---|
| RT-1 | Real script generation | `echoface make --topic "..." --until script` with Ollama running | Valid `script.json`, word count within target range | v0.1.0 |
| RT-2 | Real Piper synthesis | `voice.engine: piper`, run voice stage | `voice.wav` audible, numbers/currency spoken correctly | v0.1.0 |
| RT-3 | Real Wav2Lip + GFPGAN | `face.engine: wav2lip`, `restore: gfpgan`, full render | `face.mp4` lips move in sync frame-to-frame; GFPGAN visibly sharpens, no artefacts | v0.1.0 |
| RT-4 | Real SadTalker + inline GFPGAN | `face.engine: sadtalker`, `restore: gfpgan`, photo-only presenter | Head visibly turns/tilts; mouth syncs; no glitches | v0.1.0 |
| RT-5 | OOM retry (real) | Force a too-large `wav2lip_batch_size` on constrained VRAM | Batch size halves automatically, falls back to CPU if still OOM, job still completes | Verified via mocked-subprocess unit tests (`tests/unit/test_face_stage.py`); a genuine real-hardware OOM trigger was not separately reproduced — see `docs/project/improvements-and-known-issues.md` |
| RT-6 | Real faster-whisper captions | `captions.engine: whisper` | Word timestamps align to spoken audio; misheard words corrected to script spelling | v0.1.0 |
| RT-7 | Two-pass loudnorm, real audio | Full real render, measure with `ffmpeg -af loudnorm=...:print_format=json` and `ebur128` | Integrated loudness within ±0.5 LU of -14, true peak ≤ -1 dBTP | v0.1.0 — measured -14.09/-2.22 dBTP and -13.95/-1.69 dBTP on two renders |
| RT-8 | Real XTTS v2 | `voice.engine: xtts` | Model downloads from official HF org, synthesises real audio on GPU | v0.1.0 |
| RT-9 | `echoface doctor` on a real machine | Run with everything provisioned | All checks green except intentionally-unmet ones (e.g. `anchor1`'s missing consent) | v0.1.0 |

## Exploratory / release-checklist items
See `docs/qa/quality-checklist.md`.

## Defects found during testing
See `docs/qa/defect-log.md`.

## Requirements coverage
See `docs/qa/traceability-matrix.md` (SRS ID → test).
