# ADR-0002: Own subprocess runner scripts, not vendor CLIs or in-process imports

## Status
Accepted.

## Context
Given ADR-0001's separate venvs, the orchestrator must invoke heavy-stage
code as a subprocess. Two subprocess options existed: (a) shell out to
each vendor repo's own CLI script (`vendor/Wav2Lip/inference.py`,
`vendor/SadTalker/inference.py`) as-is, or (b) write our own driver
scripts under `scripts/` that import the vendor repos' model/pipeline
*classes* directly and own the CLI contract (arguments, output path,
failure signalling) ourselves.

## Decision
Option (b): `scripts/wav2lip_runner.py`, `scripts/gfpgan_runner.py`,
`scripts/sadtalker_runner.py`, `scripts/xtts_runner.py`. Each imports the
relevant vendor classes (`Wav2Lip`, `CropAndExtract`/`Audio2Coeff`/
`AnimateFromCoeff`, `GFPGANer`, `TTS.api.TTS`) directly, but the
orchestration, CLI flags, output-path convention, and OOM-failure
signalling are ours.

## Consequences
- **Positive**: a single `--outfile` contract across engines, regardless
  of each vendor's own (inconsistent) output-directory conventions. Real,
  persistent face-detection box caching (`BoxCache` in
  `wav2lip_runner.py`) that the vendor CLI doesn't provide. Ping-pong
  idle-loop extension and >40s audio chunking live in the orchestrator
  (`echoface/stages/face.py`) and work identically regardless of which
  runner is invoked. Failures propagate in a shape
  `run_with_oom_retry` can act on (batch-halve, then CPU fallback).
- **Negative**: more code to write and keep in sync with each vendor
  repo's internal API if it changes upstream (mitigated: vendor repos are
  pinned via `--depth 1` clone at setup time, not auto-updated).
- **Related**: unavoidable vendor-side bugs (e.g. NumPy 2.x incompatibility
  in SadTalker) are still fixed as *minimal, documented patches* in
  `vendor/patches/`, applied idempotently by `scripts/setup_windows.ps1`
  — not by forking the runner logic around the bug.
