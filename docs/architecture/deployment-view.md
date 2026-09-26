# Deployment View

Echoface is not deployed to a server — it is installed and run on a
single Windows machine the creator controls.

```mermaid
graph TB
    subgraph machine["Creator's Windows 11 machine"]
        subgraph venvs["Python venvs (local disk)"]
            v1[".venv — orchestrator"]
            v2["envs\\face — Wav2Lip/SadTalker/GFPGAN + torch cu128"]
            v3["envs\\tts — Piper/XTTS + torch cu128"]
        end
        subgraph bins["Native binaries"]
            ff["ffmpeg / ffprobe (PATH or ECHOFACE_FFMPEG_PATH)"]
        end
        subgraph data["Local filesystem"]
            models["models/ (weights, not committed)"]
            vendor["vendor/ (cloned+patched repos, not committed)"]
            assets["assets/portraits/ (presenters)"]
            consent["consent/ (signed documents)"]
            output["output/<job-id>/ (renders)"]
        end
        gpu["NVIDIA GPU (4-8+ GB VRAM, CUDA 12.8+ driver)"]
        ollama["Ollama server (localhost:11434)"]
    end

    v1 -->|subprocess| v2
    v1 -->|subprocess| v3
    v1 -->|subprocess| ff
    v2 -->|CUDA| gpu
    v3 -->|CUDA, XTTS only| gpu
    v1 -->|HTTP, localhost| ollama
    v2 --> models
    v3 --> models
    v2 --> vendor
    v1 --> assets
    v1 --> consent
    v1 --> output
```

## Provisioning
`scripts/setup_windows.ps1` is the single entry point: creates all three
venvs, installs the correct CUDA wheel index, clones+patches the vendor
repos, and prints the remaining manual steps (model weight downloads,
adding a real presenter + consent, pulling an Ollama model). It is
idempotent — safe to re-run after a partial failure or to pick up new
dependency versions.

## CI deployment (for validation, not production)
GitHub Actions runners (`ubuntu-latest`, `windows-latest`) install only
the orchestrator venv + ffmpeg — no GPU, no `envs\face`/`envs\tts`, no
model weights. This validates orchestrator logic and the dummy-engine
pipeline shape; it does not and cannot validate real inference (see
`docs/architecture/adr/0007-dummy-engines.md`).

## No cloud/service deployment exists
There is no server component, no container image, no cloud deployment
target at v0.1.0. If a future local web UI (`docs/pm/roadmap.md`) is
built, it would still run entirely on the creator's own machine.
