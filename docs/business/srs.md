# Software Requirements Specification (SRS)

Requirement IDs are referenced from `docs/qa/traceability-matrix.md` and
test names throughout `tests/`. Status reflects v0.1.0.

## 1. Functional requirements

### 1.1 Script generation

| ID | Requirement | Status | Implementation |
|---|---|---|---|
| FR-1.1 | Given a topic string and target duration, the system SHALL generate a script (title, hook, lines[], cta, description, tags[]) via a local LLM. | Done | `echoface/stages/script.py::ScriptStage`, Ollama `/api/generate` |
| FR-1.2 | The generated script SHALL be validated against a JSON schema before acceptance. | Done | `ScriptOutput` (pydantic model), `validate_script_json` |
| FR-1.3 | The script's total spoken word count SHALL be checked against the target duration (~2.6 words/sec) and regenerated (up to 3 attempts) if outside range. | Done | `target_word_range`, retry loop in `ScriptStage.run` |
| FR-1.4 | The hook SHALL be ≤ 12 words. | Done | `hook_word_count_ok` |
| FR-1.5 | A `--script-file` SHALL bypass the LLM and build a script from plain text. | Done | `script_from_plain_text` |

### 1.2 Voice synthesis

| ID | Requirement | Status | Implementation |
|---|---|---|---|
| FR-2.1 | The system SHALL synthesise the script to speech via a configurable engine (Piper default, XTTS optional, dummy for tests). | Done | `echoface/stages/voice.py`, `build_engine` |
| FR-2.2 | Numbers, currency, percentages and common abbreviations SHALL be normalised to speakable text before synthesis. | Done | `echoface/util/text.py::normalize_for_speech` |
| FR-2.3 | Segments SHALL be joined with a configurable pause, trimmed of silence, and peak-normalised. | Done | `concat_with_pauses`, `postprocess_voice` |
| FR-2.4 | A 16 kHz mono copy SHALL be produced for the face stage. | Done | `postprocess_voice` → `voice_16k.wav` |

### 1.3 Face / lip-sync

| ID | Requirement | Status | Implementation |
|---|---|---|---|
| FR-3.1 | The system SHALL animate a presenter (idle video or still photo) in sync with the voice track via a configurable engine (Wav2Lip default, SadTalker optional, dummy for tests). | Done | `echoface/stages/face.py`, `scripts/wav2lip_runner.py`, `scripts/sadtalker_runner.py` |
| FR-3.2 | On CUDA out-of-memory, the system SHALL retry with halved batch size down to a floor, then fall back to CPU. | Done | `run_with_oom_retry` |
| FR-3.3 | An idle clip shorter than the audio SHALL be extended by forward/reverse ("ping-pong") looping rather than a hard cut. | Done | `build_looped_idle_video` |
| FR-3.4 | Audio longer than a configurable threshold (default 40s) SHALL be chunked and the resulting video segments concatenated. | Done | `build_chunk_plan`, `concat_video_chunks` |
| FR-3.5 | Face-detection boxes SHALL be cached per presenter/frame-count so repeat renders skip re-detection. | Done | `FaceBoxCache` (orchestrator bookkeeping), `BoxCache` (real cache in `wav2lip_runner.py`) |
| FR-3.6 | Optional GFPGAN restoration SHALL be applied to the rendered face. | Done | `FaceStage._apply_restore`, `scripts/gfpgan_runner.py`; SadTalker applies it inline via `--enhancer gfpgan` instead |
| FR-3.7 | Ollama SHALL be asked to unload its model (`keep_alive=0`) before the face stage claims the GPU. | Done | `unload_ollama_model`, called in `FaceStage.run` |

### 1.4 Captions

| ID | Requirement | Status | Implementation |
|---|---|---|---|
| FR-4.1 | The system SHALL produce word-level timestamps from the voice audio via faster-whisper. | Done | `transcribe_words` |
| FR-4.2 | Recognised words SHALL be aligned back to the canonical script text to fix misrecognitions. | Done | `align_words_to_script` (difflib) |
| FR-4.3 | Captions SHALL render 2–3 words per event with the current word highlighted, and SHALL NOT split a group across two source lines/sentences. | Done | `group_words`, `build_ass` (karaoke `\k` tags) |
| FR-4.4 | A `dummy` captions engine SHALL evenly distribute known words across duration without any ML dependency, for CI/offline use. | Done | `generate_dummy_words` |

### 1.5 Compose

| ID | Requirement | Status | Implementation |
|---|---|---|---|
| FR-5.1 | The system SHALL assemble a single 1080x1920 @30fps H.264/AAC MP4 from background + face + captions + audio via one ffmpeg filtergraph. | Done | `echoface/stages/compose.py`, `build_compose_filtergraph` |
| FR-5.2 | The face overlay layout SHALL be selectable: `face_top`, `full_face`, `face_bottom`. | Done | `build_compose_filtergraph` |
| FR-5.3 | Background music, when configured, SHALL be mixed with optional sidechain ducking under the voice. | Done | `build_audio_premix_filtergraph` |
| FR-5.4 | Final loudness SHALL be normalised to a configurable integrated-loudness target (default -14 LUFS) via two-pass `loudnorm`, with true peak ≤ a configurable ceiling. | Done | `ComposeStage._measure_loudness`, `build_loudnorm_filter` |
| FR-5.5 | `metadata.json` SHALL always include the configured AI-disclosure line appended to the description. | Done | `ComposeStage._write_metadata` |

### 1.6 CLI / orchestration

| ID | Requirement | Status | Implementation |
|---|---|---|---|
| FR-6.1 | `echoface make` SHALL run the full pipeline for one topic or script file. | Done | `echoface/cli.py::make` |
| FR-6.2 | `echoface batch --file` SHALL run one job per line of a topics file, continuing past individual job failures. | Done | `cli.py::batch` |
| FR-6.3 | `echoface resume <job-id>` SHALL continue a job, skipping stages whose config hash and outputs are unchanged. | Done | `cli.py::resume`, `Job.is_stage_done` |
| FR-6.4 | `echoface clean <job-id> --from <stage>` SHALL invalidate that stage and every downstream stage, deleting their outputs. | Done | `cli.py::clean`, `Job.clean_from` |
| FR-6.5 | `echoface doctor` SHALL report environment/model/consent status without ever raising an unhandled exception. | Done | `echoface/doctor.py::run_doctor` |
| FR-6.6 | CLI flags SHALL override `config/*.yaml`, which SHALL be overridden by environment variables for the specific machine-bound keys in `.env.example`. | Done | `echoface/config.py::load_config`, `_apply_env_overrides` |
| FR-6.7 | Re-running `make` with an explicit `--job-id` that already exists SHALL preserve prior stage progress rather than discarding it. | Done | `Job.create` (load-if-exists path) |
| FR-6.8 | Rendering SHALL be refused for a presenter with no resolvable `consent_ref`. | Done | `check_presenter_consent`, enforced in `run_pipeline` |

## 2. Non-functional requirements

| ID | Category | Requirement | Verification |
|---|---|---|---|
| NFR-1 | Portability | Orchestrator logic SHALL run on Python 3.14 on both Windows and Linux (CI matrix); GPU stages are Windows-first per the original spec. | `.github/workflows/ci.yml` matrix |
| NFR-2 | Performance | On the reference 8 GB GPU, a ~20s Short SHALL render in well under 5 minutes end-to-end (Wav2Lip path). | Measured: ~270s total for a 22s script, see `docs/ops/performance-vram-guide.md` |
| NFR-3 | Resource constraint | The default config SHALL work within 4 GB VRAM via automatic batch-size reduction / CPU fallback on OOM. | `run_with_oom_retry`, unit-tested with mocked OOM |
| NFR-4 | Resumability | No stage SHALL redo work whose inputs (config hash) are unchanged and whose outputs still exist. | `Job.is_stage_done`, `tests/unit/test_job.py`, `tests/integration/test_compose_synthetic.py::test_compose_stage_is_idempotent_via_is_done` |
| NFR-5 | Data locality | No stage other than the script stage (local Ollama) and optional model-weight downloads SHALL make an outbound network call during a render. | Manual code audit; `docs/security/threat-model.md` |
| NFR-6 | Testability | Every stage SHALL be exercisable without a GPU via a `dummy` engine. | `config/echoface.yaml` `engine: dummy` options, `tests/e2e/test_smoke_e2e.py` |
| NFR-7 | Observability | Every job SHALL produce a `run.log` and a stage-timing summary. | `echoface/util/log.py`, `cli.py::_print_timing_table` |
| NFR-8 | Maintainability | The codebase SHALL pass `ruff check`/`ruff format --check`/`mypy` with zero errors and ≥80% branch-aware test coverage on pure-logic modules. | `.github/workflows/ci.yml` `lint` job; `pyproject.toml` `[tool.coverage]` |
| NFR-9 | Security | No secret, credential, or personally-identifying path SHALL be committed; every model download SHALL be from an official source with a recorded checksum. | `gitleaks` CI job, `models/MODELS.md` |
| NFR-10 | Consent/compliance | The consent gate (FR-6.8) SHALL be enforced in code, not merely documented. | `tests/unit/test_job.py::test_consent_check_*`, `tests/integration/test_cli_commands.py::test_make_refuses_presenter_without_consent` |

## 3. Constraints

- Target reference hardware: NVIDIA GPU, 4–8 GB VRAM, Windows 11, Python
  3.14, CUDA 12.8+ torch build (Blackwell/RTX 50-series requires cu128+).
- No paid API calls anywhere in the default pipeline.
