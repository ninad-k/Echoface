# Test Case Catalogue

Full detail lives in the test code itself (docstrings + assertions);
this is an index by area so a reviewer can find "where is X tested"
without reading every file. Counts as of v0.1.0 (105 automated tests).

| Area | File | Representative cases |
|---|---|---|
| Config loading/hashing | `tests/unit/test_config.py` | Defaults load; hash stable & order-independent; hash isolated per stage section; hash changes with global fields; invalid engine value rejected |
| Config precedence | `tests/integration/test_config_precedence.py` | default → yaml → CLI override → env var, each level proven to beat the one before it |
| Job state / idempotency | `tests/unit/test_job.py` | slugify; create/load roundtrip; skip logic (hash+file-existence combinations); clean invalidates downstream only; `Job.create` preserves state for an existing `--job-id` (regression, DEF-3); consent checks (missing meta, missing file, valid, real `anchor1` asset) |
| Text normalisation | `tests/unit/test_text.py` | numbers, currency, percent, abbreviations, symbols, idempotence on plain text |
| Script generation | `tests/unit/test_script_stage.py` | schema validation happy path; invalid JSON; missing field; hook too long; word count too low; markdown-fenced JSON; word-count range scales with duration; plain-text script building (single paragraph, multi-line, empty) |
| Captions | `tests/unit/test_captions.py` | canonical word extraction + line-id mapping; difflib alignment (exact + misrecognition fix); line-boundary-respecting grouping (regression for the "plan always Use" bug); ASS header/karaoke tags; dummy word generation |
| Face — OOM retry | `tests/unit/test_face_stage.py` | succeeds first try; halves batch size on OOM then succeeds; falls back to CPU; raises on non-OOM failure; raises when CPU also fails |
| Face — box cache | `tests/unit/test_face_stage.py` | roundtrip get/set; miss on different file |
| Face — engine selection | `tests/unit/test_face_stage.py` | `build_engine` returns correct class per config; `resolve_face_source` idle-preferred, photo-fallback, explicit-photo, raises when nothing found; SadTalker's `--enhancer` flag present only when `restore: gfpgan` |
| ffmpeg utilities | `tests/unit/test_ffmpeg_util.py` | Windows path escaping for the `ass` filter; ping-pong loop planning; chunk planning; filtergraph construction per layout; music+ducking; loudnorm JSON parsing (valid, missing keys, no JSON); single- vs two-pass filter string; audio premix (no music, ducking, custom input indices) |
| Doctor | `tests/unit/test_doctor.py` | configurable timeout default/override/garbage-value; `run_doctor` never crashes and returns a non-empty report on a bare machine |
| GPU/Ollama HTTP helpers | `tests/unit/test_gpu_util.py` | reachability true/false/exception; model list parse/empty-on-error; unload true/false (all via mocked `requests`) |
| Subprocess path resolution | `tests/unit/test_proc.py` | resolves an existing relative path to absolute; leaves a PATH-lookup name unchanged; leaves an absolute path unchanged |
| CLI commands | `tests/integration/test_cli_commands.py` | consent gate refusal (exit 2); `doctor` never crashes; `clean` on unknown job fails cleanly; `clean` correctly rewrites `job.json`; `batch` with a missing file fails cleanly |
| Compose (synthetic media) | `tests/integration/test_compose_synthetic.py` | real ffmpeg render from synthetic testsrc/sine/ASS produces a valid 1080x1920 `final.mp4` with `loudness_measured_pass1` in metadata; `is_done()`/`execute()` idempotency |
| End-to-end | `tests/e2e/test_smoke_e2e.py` | full `make` with dummy engines produces a valid final.mp4 and is idempotent on re-run; `clean` then `resume` regenerates only the cleaned stages |
