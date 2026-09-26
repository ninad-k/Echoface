# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning
follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.1] - 2026-09-26

### Fixed / CI
- **Replaced the flaky `FedericoCarboni/setup-ffmpeg@v3` Action** in
  `ci.yml` and `release.yml` — it failed twice with `TypeError: fetch
  failed` (PR #11's CI, and the v0.2.0 release run) — with each
  runner's own package manager instead (`apt-get install ffmpeg` on
  Ubuntu, `choco install ffmpeg` on Windows), each wrapped in a
  3-attempt retry with backoff. Added an explicit `ffmpeg
  -version`/`ffprobe -version` PATH check and a required
  filters/encoders check (`loudnorm`, `ass`, `sidechaincompress`
  filters; `libx264`, `aac` encoders — everything the compose stage,
  captions burn-in, and music ducking actually use) that fails the job
  loudly and by name if a distro/choco build is ever missing one. See
  DEF-14 in `docs/qa/defect-log.md`.

## [0.2.0] - 2026-09-26

A follow-up hardening pass working through every item in
`docs/project/improvements-and-known-issues.md`'s v0.1.0 backlog. See
that doc for full detail on each item (resolved-with-how, or
deferred-with-why); this section summarises what shipped.

### Changed
- **Config precedence flipped**: was `env > CLI > yaml > default`, now
  `CLI flag > environment variable (.env) > config/*.yaml > pydantic
  default` — an explicit `--flag` now always wins over an ambient
  `.env` value. See ADR-0008.
- Loudness tuning is now adaptive rather than static: `ComposeStage`
  measures the **actual final encoded file** and re-encodes once (with
  corrected offsets) if it lands outside ±0.5 LU / above the configured
  true-peak ceiling. New config fields: `compose.pre_limiter_dbfs`,
  `compose.true_peak_dbtp`, `compose.loudness_tolerance_lu`,
  `compose.loudness_hard_tp_ceiling_dbtp`,
  `compose.loudness_max_encode_attempts`. See ADR-0009.
- `echoface doctor`'s licence check is now driven by a machine-readable
  table (`models/licenses.yaml`) instead of a single hardcoded Wav2Lip
  case, and flags every active non-commercial model when
  `monetized: true`.
- The consent-gate refusal error now prints a "what to do next" block
  (presenter init, smoketest demo, docs link) instead of a bare error.
- Bumped `actions/upload-artifact` from v4 to v7 in `ci.yml` and
  `release.yml` (Dependabot #8) — inputs (`name`, `path`,
  `retention-days`) are unchanged; confirmed compatible with the
  existing `actions/download-artifact@v8` used in `release.yml`.
- Bumped `transformers` from 4.57.1 to 4.57.6 in `requirements-tts.txt`
  (Dependabot #9, still pinned `<5` per the existing CPML/XTTS
  constraint). Tested for real in `envs\tts`: a live XTTS v2 synthesis
  via `scripts/xtts_runner.py` (ffprobe-verified 24kHz mono PCM WAV,
  7.09s) and the full `tests/gpu` suite (6/6 passed, including a new
  `test_real_xtts_synthesis_tiny` regression test added to close the
  gap of XTTS having no real-GPU test coverage before this).

### Added
- **CodeFormer face restoration** (`face.restore: codeformer`) — real
  implementation against the official sczhou/CodeFormer source and
  GitHub-release weights (`scripts/codeformer_runner.py`). S-Lab
  License 1.0 (non-commercial); documented in `models/MODELS.md`,
  `docs/security/license-matrix.md`, and `models/licenses.yaml`.
- `face.restore_region: face|mouth` — mouth-only restoration with a
  feathered blend (`echoface/util/restore_blend.py`), shared by the
  GFPGAN and CodeFormer runners.
- `echoface presenter init <name>` — scaffolds
  `assets/portraits/<name>/{meta.yaml,README.md}` with a consent
  checklist, without weakening the consent gate (the scaffolded
  `consent_ref` intentionally points at a not-yet-existing file).
- `echoface prune --older-than 30d --keep-final [--delete]` — job
  output retention. Dry-run by default; deletion requires the explicit
  `--delete` flag.
- Face-box cache dedupe across a ping-pong render's forward/reverse
  halves (`fold_pingpong_index()`), avoiding redundant face detection
  on frames that are mirrors of already-detected ones.
- Real-GPU regression test tier: `tests/gpu/test_real_engines.py`
  (marked `gpu`/`ollama`/`slow`, skipped by default), runnable locally
  via `scripts/run_gpu_tests.ps1`, and a `workflow_dispatch`-only
  `.github/workflows/gpu-tests.yml` for an optional self-hosted GPU
  runner (not registered as part of this change — see the workflow
  file for how to add one).
- `tests/e2e/test_batch.py` — happy-path and failure-continuation
  coverage for `echoface batch`.
- `docs/architecture/adr/0008-config-precedence-cli-over-env.md` and
  `docs/architecture/adr/0009-loudness-robustness.md`.

### Fixed
- mypy now covers `scripts/*_runner.py` (previously excluded) — the
  project's existing `ignore_missing_imports = true` was sufficient
  once several redundant `# type: ignore` comments and a stray
  namespace-package `gfpgan/` directory at the repo root were cleaned
  up. `pyproject.toml`'s `[tool.mypy] exclude` is now just
  `["vendor/"]`.
- Several bugs found while implementing the above — see
  `docs/project/improvements-and-known-issues.md`'s "Fixed in the
  v0.2.0 pass" section for detail (a PowerShell string-encoding bug in
  the new GPU test runner, a test-fixture mismatch in the new batch
  test, and the stray `gfpgan/` directory above).
- **Permanently fixed the stray `gfpgan/weights/` directory that
  appeared at the repo root after every real GFPGAN restoration**
  (`scripts/gfpgan_runner.py`, the `tests/gpu` suite, SadTalker's
  `--enhancer gfpgan`) — root cause was `gfpgan`'s own installed
  package hardcoding a cwd-relative `model_rootpath='gfpgan/weights'`
  (see DEF-13 in `docs/qa/defect-log.md` for the full trace). Added
  `echoface/util/facexlib_pin.py`, which pins facexlib's weight
  resolution to an absolute `models/gfpgan/` instead, wired into
  `scripts/gfpgan_runner.py` and `scripts/sadtalker_runner.py`.
  `echoface/stages/face.py::_apply_restore` also now builds every
  subprocess path argument absolute and passes an explicit `cwd` (the
  job's own output dir) as defence in depth. `.gitignore` and
  `pyproject.toml`'s mypy `exclude` both guard against a leftover
  instance of `/gfpgan/`, `/weights/`, or `/results/` at the repo root
  shadowing the real package again.

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
