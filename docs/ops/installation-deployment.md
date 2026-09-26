# Installation / Deployment Guide (Windows)

This mirrors and slightly expands `README.md`'s setup section — this is
the canonical detailed version; keep both in sync if either changes.

## 1. Prerequisites
- Windows 11, NVIDIA GPU with a current driver (`nvidia-smi`). For a
  Blackwell/RTX 50-series GPU, CUDA 12.8+ is required (see ADR-0003).
- Python 3.14, 64-bit.
- [FFmpeg](https://www.gyan.dev/ffmpeg/builds/) full build, `bin` on PATH
  (or set `ECHOFACE_FFMPEG_PATH`).
- [Ollama for Windows](https://ollama.com), running (`ollama serve`).
- Git for Windows.
- 30 GB+ free disk on an SSD path with no spaces.

## 2. Orchestrator
```powershell
py -3.14 -m venv .venv
.venv\Scripts\pip install -e ".[dev,captions]"
.venv\Scripts\echoface doctor
```

## 3. Heavy-model venvs + vendor repos
```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
```
Idempotent — safe to re-run. See the script's own comments and
`docs/architecture/adr/0001-separate-venvs.md` for what it does.

Flags: `-SkipFace`, `-SkipTts`, `-SkipVendorClone` to skip parts of setup;
`-PythonExe`/`-CudaIndexUrl` to override the interpreter/CUDA wheel index.

## 4. Model weights (manual, explicit — never auto-downloaded silently)
See `models/MODELS.md` for exact URLs/checksums/licences. Summary:
- `models/wav2lip/wav2lip_gan.pth` — Wav2Lip README's Google Drive link.
- `models/gfpgan/GFPGANv1.4.pth` + facexlib detection/parsing weights —
  official GitHub releases.
- `models/piper/en_US-lessac-medium.onnx`(+.json) — official
  `rhasspy/piper-voices` HF repo.
- `vendor/SadTalker/checkpoints/*` — SadTalker README's GitHub-release
  URLs (optional, only for `face.engine: sadtalker`).
- faster-whisper / XTTS v2 weights download automatically on first use.

## 5. Ollama
```powershell
ollama serve
ollama pull qwen2.5:7b
```

## 6. Presenter + consent
Add a presenter under `assets\portraits\<name>\`, write `meta.yaml`, and
put a real signed consent document at the path it references under
`consent\`. See `docs/security/responsible-use-consent-policy.md`.

## 7. Environment variables (optional)
Copy `.env.example` to `.env` if you need any override (Ollama host,
Piper paths, ffmpeg path, HF token, XTTS licence ack). Never commit `.env`.

## 8. Verify
```powershell
.venv\Scripts\echoface doctor
```
Green except intentionally-unmet checks (e.g. the sample `anchor1`
presenter's deliberately-missing consent file).

## Uninstall / cleanup
Delete `.venv`, `envs\`, `vendor\`, `models\` (everything except
`models\MODELS.md`), and `output\`. Nothing is installed outside the
repo folder except Ollama's own model store (a separate application).

## CI/CD deployment
There is no server deployment. `.github/workflows/ci.yml` validates the
orchestrator on hosted runners (no GPU); `.github/workflows/release.yml`
builds and publishes sdist/wheel artifacts to a GitHub Release on a `v*`
tag — not installed anywhere automatically. See
`docs/architecture/deployment-view.md`.
