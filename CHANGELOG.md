# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning
follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-09-26

First public release. Milestones M1–M8 from the original design spec are
complete and verified (real-engine end to end on an RTX 5070 Laptop GPU,
8 GB VRAM).

### Added
- Full pipeline: script (Ollama) → voice (Piper/XTTS) → lip-synced face
  (Wav2Lip/SadTalker + optional GFPGAN) → captions (faster-whisper) →
  compose (ffmpeg, two-pass loudnorm).
- Typer CLI: `make`, `batch`, `resume`, `clean`, `doctor`.
- Per-stage idempotent state via `job.json` and config hashing.
- Consent gate refusing to render a presenter without an on-file
  `consent_ref`.
- `dummy` engines for every heavy stage, enabling a full GPU-free CI
  pipeline test.
- `scripts/wav2lip_runner.py`, `scripts/gfpgan_runner.py`,
  `scripts/sadtalker_runner.py`, `scripts/xtts_runner.py` — own driver
  scripts for each heavy engine (see ADR-0002).
- Two-pass `loudnorm` (measure, then linear-apply) hitting -14 LUFS ±0.5
  and ≤ -1 dBTP on real audio.
- `.env`-based configuration for machine-specific/secret-shaped values.
- CI (`ci.yml`: lint, gitleaks, pip-audit, tests on ubuntu-latest +
  windows-latest) and release (`release.yml`: sdist/wheel + GitHub
  Release on `v*` tags) workflows.
- Full SDLC documentation under `docs/` (business, PM, architecture, QA,
  dev, ops, security).
- Python 3.14 + CUDA 12.8 (cu128) torch support (Blackwell/RTX
  50-series-capable).

### Fixed
See `docs/qa/defect-log.md` for the full list found during development,
including: a voice-stage ffmpeg filtergraph input-index bug (DEF-1); a
Windows subprocess relative-path resolution failure (DEF-2); a job-state
bug that discarded prior stage progress on `--job-id` reuse (DEF-3); a
caption-grouping bug that could splice two sentences together (DEF-4);
two loudness-tuning issues on real audio (DEF-6, DEF-7); and toolchain
compatibility fixes for `basicsr` and SadTalker under Python 3.14/NumPy 2
(DEF-8, DEF-9).

### Security
- `gitleaks` scan (git history + working tree) found no secrets before
  publication.
- `.gitignore` hardened: no model weights, venvs, vendor clones, job
  outputs, or `.env` are committed.
- The `realtest` sample presenter's portrait (sourced from SadTalker's
  own example assets, unclear redistribution rights) is not committed;
  setup copies it locally instead — see `assets/ATTRIBUTION.md`.
