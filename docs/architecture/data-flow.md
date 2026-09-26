# Data Flow

```mermaid
flowchart TD
    topic[/"topic string\n(or --script-file)"/] --> script
    presenter[/"assets/portraits/<name>/\n(portrait/idle + meta.yaml)"/] --> consent{Consent gate}
    consent -- "consent_ref missing/invalid" --> refuse["Refuse: exit code 2"]
    consent -- ok --> script

    subgraph job["output/<job-id>/"]
        script["[1] SCRIPT\nOllama or plain text"] --> scriptjson[("script.json")]
        scriptjson --> voice["[2] VOICE\nPiper / XTTS / dummy"]
        voice --> voicewav[("voice.wav\nvoice_16k.wav")]
        voicewav --> face["[3] FACE\nWav2Lip / SadTalker / dummy\n+ optional GFPGAN"]
        presenter --> face
        face --> facemp4[("face.mp4")]
        voicewav --> captions["[4] CAPTIONS\nfaster-whisper + alignment"]
        scriptjson --> captions
        captions --> ass[("words.json\ncaptions.ass")]
        facemp4 --> compose["[5] COMPOSE\nffmpeg filtergraph\n+ two-pass loudnorm"]
        ass --> compose
        voicewav --> compose
        scriptjson --> compose
        compose --> final[("final.mp4\nmetadata.json")]
    end

    final --> upload[/"Creator uploads manually,\nticks synthetic-content disclosure"/]
```

## Per-stage inputs/outputs (as declared in code)

| Stage | `inputs()` | `outputs()` |
|---|---|---|
| script | `--script-file` (optional) | `script.json` |
| voice | `script.json` | `voice.wav`, `voice_16k.wav` |
| face | `voice_16k.wav` (+ presenter assets, not job-scoped) | `face.mp4` |
| captions | `voice.wav`, `script.json` | `words.json`, `captions.ass` |
| compose | `face.mp4`, `captions.ass`, `voice.wav`, `script.json` | `final.mp4`, `metadata.json` |

Every stage also implicitly depends on its own slice of `config/*.yaml`
(hashed — see `docs/architecture/adr/0005-idempotent-stage-hashing.md`)
and writes/reads through `job.json` for state tracking.

## Cross-cutting: `job.json` and `run.log`

`job.json` is written after every stage transition (started/done/failed)
and is the single source of truth `is_stage_done()` reads to decide
skip-vs-run. `run.log` accumulates every stage's rich-formatted log lines
plus the raw ffmpeg command lines the compose stage runs (via
`run_ffmpeg(..., log_path=job.run_log_path)`).
