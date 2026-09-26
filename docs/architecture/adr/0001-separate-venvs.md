# ADR-0001: Separate virtual environments per heavy stage

## Status
Accepted (from the original spec, carried through implementation).

## Context
Wav2Lip, SadTalker, GFPGAN, and Piper/XTTS each pin (or effectively
require) specific, mutually-incompatible versions of torch, numpy,
opencv, and librosa. The orchestrator itself needs none of these — it
just sequences stages, builds config, and shells out to ffmpeg.

## Decision
Three separate Python virtual environments: `.venv` (orchestrator — typer,
pydantic, rich, requests, faster-whisper), `envs\face` (Wav2Lip/SadTalker/
GFPGAN + torch/cu128), `envs\tts` (Piper/XTTS + torch/cu128 for XTTS only).
The orchestrator never imports heavy-stage code directly; it invokes the
appropriate venv's `python.exe` as a subprocess (see ADR-0002).

## Consequences
- **Positive**: orchestrator install is fast and has no GPU/torch
  dependency, so `pytest` runs on any machine including CI's
  GPU-less runners. Upgrading one stage's dependencies can't silently
  break another's.
- **Negative**: three separate `pip install` passes to provision; disk
  usage is higher (~2-3 duplicated large wheels like torch across
  `envs\face`/`envs\tts`).
- **Mitigated by**: `scripts/setup_windows.ps1` automates all three venvs
  in one idempotent script.
