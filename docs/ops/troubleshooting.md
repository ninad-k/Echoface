# Troubleshooting

Extends the original spec's troubleshooting appendix with everything
found during real implementation/verification.

| Symptom | Likely cause | Fix |
|---|---|---|
| `torch.cuda.is_available()` is False | CPU-only torch wheel, old driver, or wrong CUDA index for your GPU | Reinstall from the correct index (Blackwell/RTX 50-series needs `cu128`+, not `cu121`/`cu124` — see ADR-0003); update the NVIDIA driver; check `nvidia-smi` |
| CUDA out of memory | Batch too large, or Ollama still holding VRAM | Handled automatically (`run_with_oom_retry` halves batch, falls back to CPU) — if it still fails, lower `face.batch_size`/`face_det_batch_size` in config, or `ollama stop <model>` manually first |
| `FileNotFoundError: [WinError 2]` from a subprocess call | A relative venv path (`envs\face\Scripts\python.exe`) wasn't resolved to absolute | Fixed at the code level (`echoface/util/proc.py::resolve_exe`, DEF-2) — if you see this in your own new code, route the executable path through `resolve_exe()` |
| `pip install basicsr` / GFPGAN install fails with `KeyError: '__version__'` | `basicsr`'s sdist build breaks on Python 3.13+ (PEP 667) | Use `scripts/setup_windows.ps1` (applies `vendor/patches/patch_basicsr.py` automatically) rather than a bare `pip install basicsr` |
| SadTalker crashes with `AttributeError: module 'numpy' has no attribute 'float'` (or similar) | NumPy 2.x removed deprecated scalar-type aliases the vendored code used | Already patched by `scripts/setup_windows.ps1` (`vendor/patches/patch_sadtalker.py`) — re-run setup if you cloned `vendor/SadTalker` manually and skipped it |
| `ModuleNotFoundError: No module named 'audioop'` (pydub, via SadTalker) | `audioop` was removed from the Python 3.13+ standard library | `pip install audioop-lts` in `envs\face` (already in `requirements-face.txt`) |
| `numpy / librosa` import errors in Wav2Lip | Repo pinned to old versions | Keep it in `envs\face`; the one required patch (`librosa.filters.mel` keyword args) is applied automatically by setup — never install Wav2Lip's deps into the orchestrator venv |
| `'ffmpeg' is not recognized` | Not on PATH | Add ffmpeg's `bin` to PATH, or set `ECHOFACE_FFMPEG_PATH`; restart the terminal; run `echoface doctor` |
| Face not detected | Side profile, occlusion, tiny face | Use a front-facing, larger crop; adjust `face.pads`; check `run.log` for the S3FD/landmark error |
| Blurry mouth | Wav2Lip's 96px mouth region | Set `face.restore: gfpgan`; start from a sharper source; avoid heavy upscaling |
| Audio and lips drift | Frame-rate mismatch or VFR input | Convert idle clip to constant 25/30fps first; keep fps consistent through all stages |
| Robotic voice | Low-quality Piper voice or run-on sentences | Use a medium/high-quality Piper voice; shorter sentences; consider `voice.engine: xtts` (note: CPML non-commercial licence) |
| Captions misspell names | Whisper recognition errors | Should self-correct via script-text alignment (`align_words_to_script`) — if it still misses, the word may genuinely differ enough from the script that difflib can't match it; consider rephrasing the script |
| Piper CLI errors about unknown flags | Using old rhasspy C++ `piper.exe` flag conventions with the newer `piper-tts` pip package | `piper-tts` >= 1.8's CLI uses `-m/-c/-f`/`--length-scale` (hyphen), not the legacy `--model`/`--output_file`/`--length_scale`; `echoface`'s `PiperVoiceEngine` already uses the new convention |
| XTTS v2 hangs waiting for input in a script/CI context | Interactive CPML licence prompt | `scripts/xtts_runner.py` sets `COQUI_TOS_AGREED=1` automatically; if calling coqui-tts yourself, set that env var first |
| `echoface doctor`'s Ollama check says "not reachable" even though `ollama serve` is running | Default 3s timeout too tight under system load (e.g. right after a big test run) | Set `ECHOFACE_DOCTOR_TIMEOUT_S=10` (or higher) |
| Very slow renders | Running on CPU, or face detection re-running every time | Confirm CUDA is actually used (`device: auto`/`cuda`); the real face-box cache (`scripts/wav2lip_runner.py::BoxCache`) should make repeat renders of the same presenter/duration skip detection |
| `echoface make --job-id <existing>` seems to redo everything | Fixed (DEF-3) — was re-running everything on repeat `--job-id` use | Update to a version with the `Job.create` fix; verify with `resume` instead if still on an old build |
| Final video's loudness is off-target for unusual audio | The -9 dBFS pre-limiter / -2.5 dBTP target were tuned against two specific real renders | See `docs/architecture/adr/0004-two-pass-loudnorm.md` and `docs/project/improvements-and-known-issues.md` for the manual re-tuning procedure |
| Consent gate refuses a presenter you're sure has consent set up | `consent_ref` path is relative to the process's current working directory, not the presenter's folder | Run `echoface` from the repo root, or use an absolute path in `meta.yaml`'s `consent_ref` |
