# Test Case Catalogue

Full detail lives in the test code itself (docstrings + assertions);
this is an index by area so a reviewer can find "where is X tested"
without reading every file. Counts as of v0.2.0: 157 automated tests
total — 152 collected by default (`pytest`), plus 5 `gpu`/`ollama`-marked
real-engine tests excluded by default and run via
`scripts/run_gpu_tests.ps1`.

| Area | File | Representative cases |
|---|---|---|
| Config loading/hashing | `tests/unit/test_config.py` | Defaults load; hash stable & order-independent; hash isolated per stage section; hash changes with global fields; invalid engine value rejected |
| Config precedence | `tests/integration/test_config_precedence.py` | default → yaml → env var → CLI override, each level proven to beat the one before it (see ADR-0008) |
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
| CLI commands | `tests/integration/test_cli_commands.py` | consent gate refusal (exit 2); `doctor` never crashes; `clean` on unknown job fails cleanly; `clean` correctly rewrites `job.json`; `batch` with a missing file fails cleanly; `presenter init` scaffolds without weakening the consent gate, refuses to overwrite without `--force`; `prune` dry-run leaves files, `--delete` removes intermediates but keeps `final.mp4` |
| Compose (synthetic media) | `tests/integration/test_compose_synthetic.py` | real ffmpeg render from synthetic testsrc/sine/ASS produces a valid 1080x1920 `final.mp4` with `loudness_measured_pass1`/`loudness_measured_final` in metadata; `is_done()`/`execute()` idempotency; adaptive loudness hits spec across 4 real-ffmpeg audio profiles (quiet/hot voice, with/without music) |
| End-to-end | `tests/e2e/test_smoke_e2e.py` | full `make` with dummy engines produces a valid final.mp4 and is idempotent on re-run; `clean` then `resume` regenerates only the cleaned stages |
| Batch (e2e) | `tests/e2e/test_batch.py` | happy path renders every topic (mocked Ollama); batch continues past a single job's script-generation failure and still exits 0 |
| Model licences | `tests/unit/test_licenses.py` | `load_licenses` missing/malformed/valid; `active_models_for_config` dotted-path matching; `non_commercial_active_models` filtering; real-file smoke test confirming `models/licenses.yaml` flags the default (Wav2Lip) config |
| Prune | `tests/unit/test_prune.py` | duration parsing (days/hours/minutes, case-insensitive, garbage rejected); candidate finding respects age threshold and `keep_final`; `apply_prune` deletes correctly and leaves untouched jobs alone; `format_size` |
| Restore blending | `tests/unit/test_restore_blend.py` | mouth-region mask shape/range/feather; `blend_region` face passthrough vs. mouth blend; dtype/shape preservation; invalid region/shape rejected |
| Face-box ping-pong fold | `tests/unit/test_ffmpeg_util.py` | `fold_pingpong_index` single-frame passthrough, forward-leg identity, reverse-leg mirroring, multi-period wraparound |
| Real-engine GPU regression | `tests/gpu/test_real_engines.py` (marked `gpu`/`ollama`, excluded by default) | real Wav2Lip tiny render; real GFPGAN restoration; real CodeFormer mouth-region restoration; real Piper synthesis; real Ollama script generation — 5/5 passed via `scripts/run_gpu_tests.ps1` (63.49s) |
