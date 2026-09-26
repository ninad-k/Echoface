# Roadmap / Milestones

Milestones M1–M8 are the original build plan (see the project's master
spec). All are complete as of v0.1.0.

| Milestone | Scope | Status | Evidence |
|---|---|---|---|
| M1 | Project skeleton, config, CLI, job/state system, `doctor`, unit tests for job skipping and config hashing | Done | `echoface/{cli,config,job}.py`, `tests/unit/test_{config,job}.py` |
| M2 | Script stage: Ollama + JSON validation + prompt template | Done | `echoface/stages/script.py`, `prompts/short_default.md`, real generation verified against live Ollama (qwen2.5:7b) |
| M3 | Voice stage: Piper, text normalisation, 16 kHz copy | Done | `echoface/stages/voice.py`, `echoface/util/text.py`, real Piper synthesis verified |
| M4 | Face stage: Wav2Lip via envs\face; OOM retry; CPU fallback; idle-loop ping-pong; optional GFPGAN | Done | `scripts/wav2lip_runner.py`, `scripts/gfpgan_runner.py`, real GPU render verified (RTX 5070 Laptop) |
| M5 | Captions stage: faster-whisper + script alignment + ASS styling | Done | `echoface/stages/captions.py`, real transcription verified |
| M6 | Compose stage: FFmpeg filtergraph, layouts, ducking, loudnorm | Done, upgraded to two-pass loudnorm | `echoface/stages/compose.py`, real renders measured within ±0.5 LU of -14 LUFS |
| M7 | End-to-end smoke test; `batch` command; README | Done | `tests/e2e/test_smoke_e2e.py`, `cli.py::batch` |
| M8 | SadTalker and XTTS adapters behind the same interfaces | Done | `scripts/sadtalker_runner.py` (verified, incl. inline GFPGAN enhancer), `scripts/xtts_runner.py` (verified real synthesis; CPML non-commercial licence) |

## Post-v0.1.0 candidates (not started)

From the original spec's "Roadmap and future extensions", plus items
surfaced in `docs/project/improvements-and-known-issues.md`:

| Idea | Priority | Notes |
|---|---|---|
| CodeFormer as a second restore engine | Low | `face.restore: codeformer` currently logs a warning and no-ops; only GFPGAN is wired up |
| B-roll insertion keyed by script keywords | Medium | Would need a local stock-clip library and a keyword→clip matcher |
| Auto-generated thumbnails | Low | Frame grab + title text overlay for long-form uploads |
| YouTube Data API auto-upload (private, disclosure set) | Medium | OAuth flow, explicit user opt-in required |
| Local web UI (FastAPI + React) | Low | Queue topics, preview stages, re-render a single stage |
| Multilingual script translation + re-voice | Medium | Re-sync face stage to new audio duration |
| Diffusion-based talking-head model (8–12 GB+ VRAM path) | Low | Drop-in via the existing `FaceEngine` interface once VRAM budget allows |
| CodeFormer / better mouth-only restoration crop | Low | Current GFPGAN pass restores the whole detected face, not a mouth-only crop |
| macOS/Linux support for the heavy-model stages | Low | Orchestrator already runs cross-platform; Wav2Lip/SadTalker/Piper/XTTS installs are Windows-documented only |

## Release plan

See `docs/pm/release-plan.md`.
