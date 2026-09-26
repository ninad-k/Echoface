# Configuration Reference

Source of truth: `echoface/config.py` (pydantic models). This page mirrors
it; if they disagree, the code wins — please file an issue.

Precedence: **environment variable > CLI flag > `config/*.yaml` > pydantic
default** (see `echoface/config.py::load_config`).

## Top-level

| Key | Type | Default | Notes |
|---|---|---|---|
| `presenter` | str | `anchor1` | Folder name under `assets/portraits/` |
| `language` | str | `en` | Not currently used to select a different voice/model — reserved |
| `target_seconds` | int | `35` | Target spoken duration; drives script word-count validation |
| `monetized` | bool | `false` | If true, `doctor` warns on non-commercial model selections |

## `script:`

| Key | Type | Default | Env override |
|---|---|---|---|
| `engine` | `ollama`\|`file` | `ollama` | — |
| `model` | str | `qwen2.5:7b` | `ECHOFACE_OLLAMA_MODEL` |
| `template` | path | `prompts/short_default.md` | — |
| `temperature` | float | `0.7` | — |
| `host` | str | `http://localhost:11434` | `ECHOFACE_OLLAMA_HOST` |
| `max_retries` | int | `3` | — |

## `voice:`

| Key | Type | Default | Env override |
|---|---|---|---|
| `engine` | `piper`\|`xtts`\|`dummy` | `piper` | — |
| `piper_exe` | path | `envs/tts/Scripts/piper.exe` | `ECHOFACE_PIPER_EXE` |
| `piper_model` | path | `models/piper/en_US-lessac-medium.onnx` | `ECHOFACE_PIPER_MODEL` |
| `speed` | float | `1.05` | — |
| `pause_ms` | int | `350` | Silence between hook/lines/cta segments |
| `xtts_speaker_wav` | path\|null | `null` | Reference clip for XTTS cloning — **only with written voice consent** |

## `face:`

| Key | Type | Default | Notes |
|---|---|---|---|
| `engine` | `wav2lip`\|`sadtalker`\|`dummy` | `wav2lip` | |
| `source` | `idle`\|`photo` | `idle` | SadTalker only accepts `photo` |
| `restore` | `none`\|`gfpgan`\|`codeformer` | `gfpgan` | `codeformer` accepted but not implemented (logs a warning, no-ops) |
| `batch_size` | int | `32` | Wav2Lip only; SadTalker hardcodes 1 (spec's 4GB-safe value) regardless of this |
| `face_det_batch_size` | int | `8` | Wav2Lip's S3FD detector batch |
| `device` | `auto`\|`cuda`\|`cpu` | `auto` | `auto` probes `nvidia-smi` |
| `resize_factor` | int | `1` | Wav2Lip input downscale factor |
| `pads` | `[int,int,int,int]` | `[0,15,0,0]` | top/bottom/left/right face-crop padding |
| `chunk_seconds` | float | `40` | Audio longer than this is chunked and concatenated |

## `captions:`

| Key | Type | Default |
|---|---|---|
| `engine` | `whisper`\|`dummy` | `whisper` |
| `model` | str | `small` (faster-whisper model size) |
| `device` | str | `cpu` |
| `compute_type` | str | `int8` |
| `style` | str | `bold_center` (currently informational; ASS style is fixed) |
| `max_words_per_line` | int | `3` |
| `font` | str | `Arial` |
| `font_size` | int | `96` |

## `compose:`

| Key | Type | Default | Notes |
|---|---|---|---|
| `width` / `height` | int | `1080` / `1920` | |
| `fps` | int | `30` | |
| `layout` | `face_top`\|`full_face`\|`face_bottom` | `face_top` | |
| `background` | path\|null | `null` | Falls back to a generated solid colour if unset/missing |
| `background_color` | str | `0x101018` | ffmpeg colour spec for the fallback |
| `music` | path\|null | `null` | |
| `music_volume_db` | float | `-20` | |
| `duck_under_voice` | bool | `true` | Sidechain-compress music under voice |
| `loudness_lufs` | float | `-14` | Two-pass loudnorm integrated-loudness target |
| `true_peak_dbtp` | float | `-2.5` | Pre-encode TP ceiling — see ADR-0004 for why it's lower than the -1 dBTP final spec |
| `loudness_lra` | float | `11` | Loudness range target |
| `crf` | int | `19` | libx264 CRF |
| `disclosure_line` | str | `Presenter is AI-generated.` | Always appended to `metadata.json`'s description |

## Environment variables (`.env`, see `.env.example`)

| Variable | Overrides | Required? |
|---|---|---|
| `ECHOFACE_OLLAMA_HOST` | `script.host` | No |
| `ECHOFACE_OLLAMA_MODEL` | `script.model` | No |
| `ECHOFACE_PIPER_EXE` | `voice.piper_exe` | No |
| `ECHOFACE_PIPER_MODEL` | `voice.piper_model` | No |
| `ECHOFACE_FFMPEG_PATH` | ffmpeg/ffprobe binary resolution | No (falls back to PATH) |
| `ECHOFACE_DOCTOR_TIMEOUT_S` | `doctor`'s Ollama-probe timeout (default 3s) | No |
| `HF_TOKEN` | Hugging Face Hub auth (read by `huggingface_hub` directly) | No — only for gated/rate-limited models |
| `COQUI_TOS_AGREED` | Skips XTTS v2's interactive CPML licence prompt | Set automatically by `scripts/xtts_runner.py`; only needed manually if you call the runner differently |

## CLI flags
See `echoface make/batch/resume/clean/doctor --help`, or
`docs/user-manual.md`'s command reference.
