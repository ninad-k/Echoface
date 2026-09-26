# RAID Log (Risks, Assumptions, Issues, Dependencies)

Last updated: v0.1.0 publication pass.

## Risks

| ID | Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|---|
| R-1 | GitHub-hosted Windows/Ubuntu runners lack a GPU, so CI can never validate real Wav2Lip/SadTalker/GFPGAN inference | Certain | Medium | `dummy` engines + e2e smoke test give CI-safe coverage of the pipeline *shape*; real-engine verification stays a manual, documented process (`docs/qa/test-plan.md`) run on the maintainer's GPU machine | Maintainer |
| R-2 | Wav2Lip's default checkpoint is research/non-commercial licensed | Certain (current default) | High if monetised without checking | `echoface doctor` warns when `monetized: true` + a non-commercial engine selected; `docs/security/license-matrix.md` documents every model | Maintainer |
| R-3 | The -9 dBFS voice pre-limiter / -2.5 dBTP loudnorm target were tuned against two specific real renders (Piper, ~20s each) | Medium | Medium — different content (other TTS engines, music-heavy renders, much longer scripts) could need re-tuning | Documented in `README.md` and `docs/project/improvements-and-known-issues.md`; the tuning method (manual `ffmpeg -af loudnorm=...:print_format=json` experiment) is written down for repeatability | Maintainer |
| R-4 | Vendored Wav2Lip/SadTalker repos are unmaintained research code; future NumPy/torch releases could reintroduce compatibility breaks | Medium | Medium | Every fix is a documented, idempotent patch in `vendor/patches/`, not an in-place edit lost on re-clone | Maintainer |
| R-5 | Ollama server not running / model not pulled is a common first-run failure mode | High | Low (clear error) | `echoface doctor` checks reachability + model presence with an actionable message | Maintainer |
| R-6 | Public repo — any future contributor could accidentally commit a real consent document, model weight, or personal path | Low | High (privacy/IP) | `.gitignore` coverage, `gitleaks` in pre-commit + CI, `docs/security/threat-model.md` | Maintainer + contributors |

## Assumptions

| ID | Assumption | Status |
|---|---|---|
| A-1 | Users of the heavy-model stages run Windows 11 with an NVIDIA GPU | Holds for the verified path; orchestrator itself is cross-platform |
| A-2 | Python 3.14 wheels exist for every heavy dependency (torch, opencv, librosa, etc.) | Verified true at v0.1.0 provisioning time on this machine; may not hold for niche future dependencies |
| A-3 | Ollama, ffmpeg, and Piper are installed/managed by the user outside pip | Documented in `docs/ops/installation-deployment.md` |
| A-4 | A single local user runs one job at a time (no concurrency/locking around `output/<job-id>/`) | True of current design; not a multi-tenant tool |

## Issues (known, open)

| ID | Issue | Severity | Tracking |
|---|---|---|---|
| I-1 | `face.restore: codeformer` was accepted by config but not implemented (logged a warning, no-op) | Low | **Resolved in v0.2.0** — real implementation, `scripts/codeformer_runner.py`; see `docs/project/improvements-and-known-issues.md` #2 |
| I-2 | `anchor1` sample presenter intentionally has no valid consent file, which is correct for its purpose but can confuse a new user who tries to render with it directly | Low | **Resolved in v0.2.0** — friendlier refusal message + `echoface presenter init`; see improvements doc #5 |
| I-3 | Doctor's Ollama-reachability check used a fixed 3s timeout that occasionally false-negatived under load | Low | Fixed in v0.1.0 pass — now `ECHOFACE_DOCTOR_TIMEOUT_S`-configurable, default unchanged |
| I-4 | mypy was not run on `scripts/*_runner.py` (excluded) since they import optional heavy deps (torch/cv2) not installed in the orchestrator's type-check env | Low | **Resolved in v0.2.0** — exclude list dropped to just `vendor/`; see improvements doc #10 |
| I-5 | No job output retention/pruning — `output/<job-id>/` accumulates indefinitely | Low | **Resolved in v0.2.0** — `echoface prune`; see improvements doc #7 |
| I-6 | Face-box cache didn't dedupe across a ping-pong render's forward/reverse halves | Low | **Resolved in v0.2.0**, with a documented gap — see improvements doc #8 (wiring not independently GPU-re-verified on a real ping-pong render) |
| I-7 | No automated real-GPU regression tests — engine verification was manual/checklist-only | Medium | **Resolved in v0.2.0** — `tests/gpu/`, `scripts/run_gpu_tests.ps1`, `gpu-tests.yml`; see improvements doc #4 |

## Dependencies

| ID | Dependency | Type | Notes |
|---|---|---|---|
| D-1 | Ollama (external application) | Runtime | Script stage; must be running with a model pulled |
| D-2 | ffmpeg/ffprobe | Runtime | Voice post-processing, face chunking/looping, compose; `ECHOFACE_FFMPEG_PATH` override available |
| D-3 | Rudrabha/Wav2Lip, OpenTalker/SadTalker, TencentARC/GFPGAN (vendored, not committed) | Runtime (face stage) | Cloned by `scripts/setup_windows.ps1`; patches in `vendor/patches/` |
| D-4 | rhasspy/piper-voices, Systran/faster-whisper, coqui/XTTS-v2 (Hugging Face) | Runtime (model weights) | Downloaded per `models/MODELS.md`; XTTS is CPML non-commercial |
| D-5 | GitHub Actions hosted runners | CI/CD | ubuntu-latest, windows-latest; see R-1 for GPU limitation |
