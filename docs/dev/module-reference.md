# Module / API Reference

High-level map of the `echoface` package. For full signatures, read the
source — every public function has a docstring; this page is the index.

## `echoface/cli.py`
Typer app. Commands: `make`, `batch`, `resume`, `clean`, `doctor`.
`run_pipeline(job, cfg, ...)` is the shared driver: enforces the consent
gate, then runs each `Stage` in `STAGE_ORDER`, prints the timing table.

## `echoface/config.py`
- `EchofaceConfig` (root pydantic model) with nested `ScriptConfig`,
  `VoiceConfig`, `FaceConfig`, `CaptionsConfig`, `ComposeConfig`.
- `load_config(path, overrides) -> EchofaceConfig`: yaml → env var
  overrides → CLI overrides → validation. CLI flag beats env var beats
  yaml beats pydantic default (see ADR-0008).
- `stage_hash(cfg, stage_name, extra) -> str`: the idempotency hash (see
  ADR-0005).

## `echoface/job.py`
- `Job` (dataclass): job folder, `job.json` I/O, `is_stage_done`,
  `clean_from`, `mark_started/done/failed`.
- `Job.create(...)`: creates a new job, or loads an existing one if
  `job_id` already has a `job.json` (see DEF-3 in the defect log).
- `check_presenter_consent(presenter) -> dict`: raises `ConsentError` if
  the gate fails; returns the parsed `meta.yaml` dict on success.

## `echoface/doctor.py`
- `run_doctor(cfg) -> list[Check]`: every individual `_check_*` function
  is wrapped so one failure can't crash the report.
- `_doctor_timeout()`: reads `ECHOFACE_DOCTOR_TIMEOUT_S`.

## `echoface/stages/base.py`
- `Stage` (ABC): `inputs()`, `outputs()`, `extra_hash_inputs()`, `run()`
  abstract/overridable; `current_hash()`, `is_done()`, `execute()`
  concrete (shared skip/timing/state logic every stage gets for free).

## `echoface/stages/script.py`
- `ScriptOutput` (pydantic schema for the LLM's JSON).
- `validate_script_json(raw, target_seconds) -> ScriptOutput`.
- `script_from_plain_text(text, topic) -> ScriptOutput`: `--script-file` path.
- `call_ollama(host, model, prompt, temperature) -> str`.
- `ScriptStage(Stage)`.

## `echoface/stages/voice.py`
- `VoiceEngine` (ABC) with `PiperVoiceEngine`, `XttsVoiceEngine`,
  `DummyVoiceEngine`.
- `build_engine(cfg) -> VoiceEngine`.
- `concat_with_pauses(segment_wavs, pause_ms, out_wav)`.
- `postprocess_voice(raw_wav, final_wav, wav16k)`: silence trim, peak
  normalise, 16 kHz copy.
- `VoiceStage(Stage)`.

## `echoface/stages/face.py`
- `FaceEngine` (ABC) with `Wav2LipEngine`, `SadTalkerEngine`,
  `DummyFaceEngine`.
- `run_with_oom_retry(build_cmd, initial_batch_size, device, ...)`: the
  shared OOM-halve/CPU-fallback contract every real engine uses.
- `FaceBoxCache`: orchestrator-side bookkeeping cache (the *real*
  per-frame box cache lives in `scripts/wav2lip_runner.py::BoxCache`).
- `build_looped_idle_video`, `concat_video_chunks`: ping-pong/chunk
  helpers.
- `resolve_face_source`, `build_engine`.
- `FaceStage(Stage)`.

## `echoface/stages/captions.py`
- `Word` (dataclass, carries `line_id` for boundary-safe grouping).
- `canonical_words`, `canonical_word_line_ids`.
- `transcribe_words` (lazy `faster_whisper` import).
- `align_words_to_script`: difflib-based spelling correction.
- `generate_dummy_words`: no-ML fallback.
- `group_words`, `build_ass`.
- `CaptionsStage(Stage)`.

## `echoface/stages/compose.py`
- `resolve_background`.
- `ComposeStage(Stage)`: `_measure_loudness` (pass 1), `run()` (pass 2 +
  encode), `_write_metadata`.

## `echoface/util/ffmpeg.py`
- `probe`, `run_ffmpeg`, `escape_filter_path`.
- `build_ping_pong_plan`, `build_chunk_plan`.
- `build_audio_premix_filtergraph`, `build_compose_filtergraph`.
- `LoudnormMeasurement`, `parse_loudnorm_json`, `build_loudnorm_filter`.

## `echoface/util/gpu.py`
- `GpuInfo`, `detect_gpu()` (via `nvidia-smi`, not torch — orchestrator
  has no torch, see ADR-0001).
- `unload_ollama_model`, `ollama_reachable`, `ollama_models`.

## `echoface/util/text.py`
- `normalize_for_speech(text) -> str`: numbers/currency/percent/
  abbreviations/symbols to speakable words, stdlib-only (no num2words).
- `word_count`.

## `echoface/util/proc.py`
- `resolve_exe(path) -> str`: the DEF-2 fix, resolves a relative venv
  executable path to absolute for Windows `subprocess` compatibility.

## `echoface/util/env.py`
- `load_env()`: loads `.env` via python-dotenv, called once at CLI startup.

## `echoface/util/log.py`
- `get_logger`, `attach_job_log_file`, `detach_handler`.

## `scripts/*_runner.py`
Subprocess entry points invoked by the face/voice stages inside
`envs\face`/`envs\tts` — see ADR-0002 and each file's own module
docstring for what it does and which vendor patches it depends on.
