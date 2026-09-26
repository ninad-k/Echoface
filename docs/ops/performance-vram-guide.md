# Performance and VRAM Guide

## Reference measurements (real, this project's verification machine)

Hardware: NVIDIA RTX 5070 Laptop GPU, 8 GB VRAM, torch 2.11+cu128, Python
3.14. Scripts ~18-22 seconds of spoken audio.

| Stage | Engine | Time |
|---|---|---|
| Script | Ollama qwen2.5:7b | 5.5s – 17.4s (varies with retry attempts) |
| Voice | Piper | 14 – 26s |
| Face | Wav2Lip, batch_size=32, + GFPGAN | ~115 – 143s |
| Face | SadTalker, no enhancer | ~85s |
| Face | SadTalker, `--enhancer gfpgan` | ~242s (4 min) |
| Captions | faster-whisper small, CPU int8 | 7 – 17s |
| Compose | incl. two-pass loudnorm | 4.5 – 18s |
| **Total (Wav2Lip path)** | | **~270s (4.5 min)** |
| **Total (SadTalker + GFPGAN path)** | | **~270s (4.5 min)**, dominated by the enhancer pass |

## VRAM guidance

- **4 GB GPU** (spec's baseline target): halve `face.batch_size` and
  `face.face_det_batch_size` from the 8GB defaults (32→16, 8→4);
  `run_with_oom_retry` will further auto-halve on a real OOM down to a
  floor, then fall back to CPU as a last resort — this is automatic, no
  config change strictly required, but starting lower avoids the retry
  overhead.
- **8 GB GPU** (verified): the shipped defaults (`batch_size: 32`,
  `face_det_batch_size: 8`) have headroom to spare.
- **One GPU stage at a time**: the face stage asks Ollama to unload its
  model (`keep_alive=0`) before claiming the GPU
  (`unload_ollama_model` in `FaceStage.run`) — don't run a second
  GPU-heavy process concurrently with a render.
- **SadTalker's `--enhancer gfpgan`** roughly triples render time (256px
  → 512px output, per-frame GFPGAN pass) — use `restore: none` for faster
  iteration, `gfpgan` for final output quality.
- **XTTS v2** needs ~3-4 GB VRAM on top of whatever else is loaded; first
  load takes ~90s including a ~1.8 GB one-time model download.

## Speeding up repeat renders
- Face-detection box caching (`scripts/wav2lip_runner.py::BoxCache`) skips
  S3FD re-detection on a repeat render of the same presenter at the same
  audio-derived frame count — this is often the slowest part of a cold
  Wav2Lip run.
- Idempotent stage skipping (ADR-0005): `resume` never redoes a stage
  whose config hash and outputs are unchanged.

## Long-audio handling
Audio longer than `face.chunk_seconds` (default 40s) is split into
chunks, each rendered separately, then concatenated — keeps per-chunk
memory bounded regardless of total Short length. Chunk boundaries are
pure ffmpeg `-ss`/`-t` trims plus a concat-demuxer join (no re-encode
between chunks beyond what each engine itself produces).

## CPU-only fallback
Every real engine has a CPU path (`run_with_oom_retry`'s final fallback,
or `device: cpu` set explicitly). Expect an order of magnitude slower —
CPU-only isn't a recommended steady-state, just a "still finishes rather
than crashing" safety net.
