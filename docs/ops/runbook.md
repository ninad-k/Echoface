# Runbook

Operational procedures for running Echoface day-to-day. For error-message
lookup, see `docs/ops/troubleshooting.md`.

## Standard render
```powershell
.venv\Scripts\echoface doctor                     # confirm environment first
.venv\Scripts\echoface make --topic "..." --presenter <name>
```

## Overnight batch
```powershell
.venv\Scripts\echoface batch --file topics.txt --presenter <name>
```
Each line's job continues independently on failure — check console output
for any `Job <id> failed:` lines afterward, then inspect that job's
`output/<id>/run.log`.

## Resuming after an interruption (power loss, closed terminal, etc.)
```powershell
.venv\Scripts\echoface resume <job-id>
```
Already-completed stages (matching config hash + existing output files)
are skipped automatically.

## Re-rendering just the ending
```powershell
.venv\Scripts\echoface clean <job-id> --from captions
.venv\Scripts\echoface resume <job-id>
```

## Freeing VRAM stuck between runs
The face stage already asks Ollama to unload its model
(`keep_alive=0`) before claiming the GPU. If VRAM still looks high:
```powershell
ollama stop <model-name>
nvidia-smi   # confirm VRAM is freed
```

## Checking a job's health
```powershell
type output\<job-id>\job.json    # per-stage status/hash/duration
type output\<job-id>\run.log     # full log incl. raw ffmpeg commands
```

## Verifying a finished render
```powershell
ffprobe -v error -show_entries stream=width,height,r_frame_rate output\<job-id>\final.mp4
ffmpeg -i output\<job-id>\final.mp4 -af ebur128 -f null -   # loudness check
```
Expect 1080x1920, 30fps; integrated loudness within ±0.5 LU of the
configured `compose.loudness_lufs` (default -14).

## Rotating/updating the Ollama model
```powershell
ollama pull qwen2.5:7b            # or a different model
# then set script.model (config/echoface.yaml or --topic run) to match
```

## Disk space management
`output/<job-id>/` keeps every stage's intermediate artifact (useful for
`clean`/`resume`). To reclaim space for old, finished jobs you don't plan
to re-render, delete the job folder entirely — there's no built-in
retention/pruning command at v0.1.0 (see
`docs/project/improvements-and-known-issues.md`).

## Incident: a render silently used the wrong config
Check `job.json`'s recorded `config_hash` per stage against
`stage_hash(cfg, stage_name)` for your current config
(`python -c "from echoface.config import load_config, stage_hash; c=load_config(); print(stage_hash(c,'compose'))"`)
— a mismatch means that stage *will* re-run on the next `resume`, which is
the expected self-correcting behaviour (see ADR-0005).
