# Software Architecture (C4)

## Level 1: System Context

```mermaid
C4Context
    Person(creator, "Creator", "Runs the CLI to produce a Short")
    System(echoface, "Echoface", "Local CLI: topic -> script -> voice -> lip-synced face -> captioned 9:16 video")
    System_Ext(ollama, "Ollama", "Local LLM server (script generation)")
    System_Ext(hf, "Hugging Face Hub", "One-time model weight downloads (faster-whisper, XTTS)")
    System_Ext(platforms, "YouTube / Reels / TikTok", "Where the finished video is manually uploaded")

    Rel(creator, echoface, "Runs echoface make/batch/resume/clean/doctor")
    Rel(echoface, ollama, "POST /api/generate (topic only)", "HTTP, localhost")
    Rel(echoface, hf, "Downloads model weights (first run only)", "HTTPS")
    Rel(creator, platforms, "Manually uploads final.mp4, ticks synthetic-content disclosure")
```

Echoface is a **local CLI**, not a service. It has no inbound network
interface. Its only outbound calls are to a local Ollama instance (script
stage) and, on first use of an engine, to Hugging Face Hub for model
weights — never carrying user media.

## Level 2: Containers

```mermaid
C4Container
    Person(creator, "Creator")
    Container_Boundary(echoface, "Echoface (single machine)") {
        Container(cli, "Orchestrator", "Python 3.14, .venv", "Typer CLI, config, job state, stage sequencing")
        Container(faceenv, "envs\\face", "Python 3.14, torch+cu128", "Wav2Lip/SadTalker/GFPGAN subprocess runners")
        Container(ttsenv, "envs\\tts", "Python 3.14", "Piper/XTTS subprocess runners")
        Container(ffmpeg, "ffmpeg/ffprobe", "native binary", "Audio/video encode, filtergraphs, probing")
        ContainerDb(jobstore, "output/<job-id>/", "filesystem", "job.json, per-stage artifacts, run.log")
        ContainerDb(models, "models/, vendor/", "filesystem", "Downloaded weights, vendored+patched repos")
    }
    System_Ext(ollama, "Ollama")

    Rel(creator, cli, "CLI commands")
    Rel(cli, ollama, "HTTP")
    Rel(cli, faceenv, "subprocess (python.exe scripts\\*.py)")
    Rel(cli, ttsenv, "subprocess")
    Rel(cli, ffmpeg, "subprocess")
    Rel(cli, jobstore, "read/write")
    Rel(faceenv, models, "reads checkpoints")
    Rel(ttsenv, models, "reads checkpoints")
```

**Why separate venvs and subprocesses**: see
`docs/architecture/adr/0001-separate-venvs.md` and
`.../0002-subprocess-runners.md`.

## Level 3: Components (Orchestrator)

```mermaid
C4Component
    Container_Boundary(cli_container, "Orchestrator (echoface package)") {
        Component(cliC, "cli.py", "Typer app", "make/batch/resume/clean/doctor commands, run_pipeline()")
        Component(config, "config.py", "pydantic", "YAML + env + CLI override merge, per-stage config hash")
        Component(job, "job.py", "dataclasses", "Job/job.json state, is_stage_done, clean_from, consent gate")
        Component(doctor, "doctor.py", "-", "Environment checks (never raises)")
        Component(base, "stages/base.py", "ABC", "Stage interface: is_done()/execute()/run()")
        Component(script, "stages/script.py", "-", "Ollama client, schema+word-count validation")
        Component(voice, "stages/voice.py", "-", "Piper/XTTS/dummy engines, text normalisation, concat")
        Component(face, "stages/face.py", "-", "Wav2Lip/SadTalker/dummy engines, OOM retry, chunk/loop planning")
        Component(captions, "stages/captions.py", "-", "faster-whisper, script alignment, ASS generation")
        Component(compose, "stages/compose.py", "-", "Filtergraph build, two-pass loudnorm, metadata")
        Component(util, "util/*.py", "-", "ffmpeg, gpu, text, proc, env, log helpers")
    }

    Rel(cliC, config, "load_config()")
    Rel(cliC, job, "Job.create/load, check_presenter_consent")
    Rel(cliC, doctor, "run_doctor()")
    Rel(cliC, base, "instantiates + calls execute() per stage")
    Rel(base, script, "")
    Rel(base, voice, "")
    Rel(base, face, "")
    Rel(base, captions, "")
    Rel(base, compose, "")
    Rel(script, util, "text normalisation")
    Rel(voice, util, "ffmpeg concat/postprocess")
    Rel(face, util, "ffmpeg chunk/loop, gpu detect/unload")
    Rel(compose, util, "ffmpeg filtergraph, loudnorm")
```

Every stage implements the same interface (`Stage` in `stages/base.py`):
`inputs()`, `outputs()`, `is_done()`, `run()`. `execute()` wraps `run()`
with timing, job-state updates, and skip logic — see
`docs/architecture/job-state-machine.md`.

## Data flow

See `docs/architecture/data-flow.md` for the artifact-by-artifact pipeline
diagram.

## Deployment view

See `docs/architecture/deployment-view.md`.

## Architecture Decision Records

See `docs/architecture/adr/` — one ADR per significant decision:

- [0001 — Separate venvs per heavy stage](adr/0001-separate-venvs.md)
- [0002 — Subprocess runner scripts, not in-process imports](adr/0002-subprocess-runners.md)
- [0003 — Python 3.14 + CUDA 12.8 (cu128)](adr/0003-python-3.14-cu128.md)
- [0004 — Two-pass loudnorm](adr/0004-two-pass-loudnorm.md)
- [0005 — Idempotent stage hashing](adr/0005-idempotent-stage-hashing.md)
- [0006 — Consent gate as a code-level check](adr/0006-consent-gate.md)
- [0007 — Dummy engines for GPU-free testing](adr/0007-dummy-engines.md)
