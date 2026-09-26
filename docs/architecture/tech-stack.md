# Tech Stack

## Orchestrator (`.venv`)
| Component | Choice | Why |
|---|---|---|
| Language | Python 3.14 | See ADR-0003 |
| CLI framework | Typer | Declarative, type-hinted CLI with good `--help`, used via `CliRunner` in tests |
| Config validation | Pydantic v2 | Schema validation, `.model_dump()` for hashing, clear error messages |
| Console/logging | Rich | Tables (doctor report, stage timings), styled console + file logging |
| HTTP client | requests | Ollama API calls |
| Env loading | python-dotenv | Optional `.env` support, see `.env.example` |
| Testing | pytest, pytest-cov | Unit/integration/e2e suite, coverage gating |
| Lint/format | ruff | Single tool for both, fast |
| Types | mypy | Orchestrator package only (heavy runners excluded, see ADR-0003) |

## Face stage (`envs\face`)
torch/torchvision/torchaudio (cu128), opencv-python, librosa, resampy,
scipy, face-alignment, facexlib, kornia, yacs, pydub, safetensors,
basicsr (patched), gfpgan, audioop-lts (Python 3.13+ stdlib removal
backport, needed by SadTalker's pydub use).

## TTS stage (`envs\tts`)
piper-tts (pip package, replaces the old rhasspy C++ binary), coqui-tts
(actively-maintained fork of the archived coqui-ai/TTS, for XTTS v2),
torch/torchaudio (cu128, XTTS only), torchcodec, transformers (pinned
`<5` — coqui-tts's tortoise/XTTS layers use a function transformers 5.x
removed).

## External tools
ffmpeg/ffprobe (full build), Ollama (qwen2.5:7b default model), git (for
vendor repo cloning).

## Vendored ML repos (`vendor/`, not committed — cloned by setup)
Rudrabha/Wav2Lip, OpenTalker/SadTalker, TencentARC/GFPGAN — see
`docs/security/license-matrix.md` for licences and
`vendor/patches/` for the compatibility fixes applied.

## CI/CD
GitHub Actions (`ci.yml`, `release.yml`), gitleaks, pip-audit, Dependabot,
`FedericoCarboni/setup-ffmpeg` and `softprops/action-gh-release` actions.

## Why not X?

- **Not a web framework / service**: Echoface is a local CLI by design
  (see BRD objective BO-2 — no third-party cloud). Adding FastAPI etc. is
  a roadmap item, not a current dependency.
- **Not MoviePy for compose**: the spec explicitly favours a single ffmpeg
  filtergraph over MoviePy for simplicity and speed; that choice was kept.
- **Not the original coqui-ai/TTS package**: archived/unmaintained, no
  Python 3.14 wheels; the community-maintained `coqui-tts` fork was used
  instead (see ADR-0003 context on dependency verification).
