# Requirements Traceability Matrix

SRS ID (see `docs/business/srs.md`) → automated test(s). "Manual" =
verified per `docs/qa/test-plan.md`'s real-engine table (RT-#), not
automatable in CI.

| SRS ID | Requirement (short) | Test(s) |
|---|---|---|
| FR-1.1 | Script generation via local LLM | `tests/unit/test_script_stage.py` (validation logic); RT-1 (real call) |
| FR-1.2 | Script JSON schema validation | `test_script_stage.py::test_validate_script_json_*` |
| FR-1.3 | Word-count-vs-duration retry | `test_script_stage.py::test_validate_script_json_rejects_wrong_word_count`, `test_target_word_range_scales_with_seconds` |
| FR-1.4 | Hook ≤ 12 words | `test_script_stage.py::test_validate_script_json_rejects_long_hook` |
| FR-1.5 | `--script-file` bypasses LLM | `test_script_stage.py::test_script_from_plain_text_*`; `tests/e2e/test_smoke_e2e.py` |
| FR-2.1 | Configurable voice engine | `echoface/stages/voice.py::build_engine`; RT-2, RT-8 |
| FR-2.2 | Text normalisation | `tests/unit/test_text.py` (all cases) |
| FR-2.3 | Segment join/trim/peak-normalise | `tests/e2e/test_smoke_e2e.py` (dummy engine exercises `concat_with_pauses`/`postprocess_voice`) |
| FR-2.4 | 16 kHz copy | `tests/e2e/test_smoke_e2e.py` (asserts `voice_16k.wav` produced) |
| FR-3.1 | Configurable face engine | `tests/unit/test_face_stage.py::test_build_engine_returns_correct_class`; RT-3, RT-4 |
| FR-3.2 | OOM retry + CPU fallback | `test_face_stage.py::test_run_with_oom_retry_*` |
| FR-3.3 | Ping-pong idle-loop extension | `tests/unit/test_ffmpeg_util.py::test_build_ping_pong_plan_*` |
| FR-3.4 | Audio chunking for >40s | `test_ffmpeg_util.py::test_build_chunk_plan_*` |
| FR-3.5 | Face-box caching | `test_face_stage.py::test_face_box_cache_roundtrip` |
| FR-3.6 | GFPGAN restoration | `test_face_stage.py::test_sadtalker_engine_passes_enhancer_flag_*`; RT-3, RT-4 |
| FR-3.7 | Ollama unload before face stage | `tests/unit/test_gpu_util.py::test_unload_ollama_model_*`; code path in `FaceStage.run` |
| FR-4.1 | Word-level timestamps | RT-6 (real faster-whisper) |
| FR-4.2 | Script-text alignment | `tests/unit/test_captions.py::test_align_words_to_script_*` |
| FR-4.3 | 2-3 word groups, no cross-line splice | `test_captions.py::test_group_words_*`, `test_build_ass_*` |
| FR-4.4 | Dummy captions engine | `test_captions.py::test_generate_dummy_words_*` |
| FR-5.1 | Single-filtergraph 1080x1920 h264/aac compose | `tests/integration/test_compose_synthetic.py::test_compose_stage_produces_valid_final_mp4` |
| FR-5.2 | Selectable layouts | `tests/unit/test_ffmpeg_util.py::test_build_compose_filtergraph_layouts` |
| FR-5.3 | Music mix + ducking | `test_ffmpeg_util.py::test_build_audio_premix_filtergraph_with_ducking` |
| FR-5.4 | Two-pass loudnorm within spec | `test_ffmpeg_util.py::test_parse_loudnorm_json_*`, `test_build_loudnorm_filter_*`; RT-7 (real measurement) |
| FR-5.5 | Disclosure line in metadata | `test_compose_synthetic.py` asserts it; `tests/e2e/test_smoke_e2e.py` asserts it |
| FR-6.1 | `make` command | `tests/e2e/test_smoke_e2e.py` |
| FR-6.2 | `batch` command | `tests/integration/test_cli_commands.py::test_batch_missing_file_fails_cleanly` (happy path exercised manually/via code review — see improvements list for a gap) |
| FR-6.3 | `resume` skip logic | `tests/unit/test_job.py::test_stage_skip_logic`; `tests/e2e/test_smoke_e2e.py::test_clean_then_resume` |
| FR-6.4 | `clean --from` | `test_job.py::test_clean_invalidates_downstream`; `tests/integration/test_cli_commands.py::test_clean_resets_job_json_stage_status` |
| FR-6.5 | `doctor` never crashes | `tests/unit/test_doctor.py::test_run_doctor_never_crashes_and_returns_checks`; `tests/integration/test_cli_commands.py::test_doctor_exits_zero_with_only_warnings` |
| FR-6.6 | Config override precedence | `tests/integration/test_config_precedence.py` (all 5 cases) |
| FR-6.7 | `--job-id` reuse preserves state | `test_job.py::test_create_with_existing_job_id_preserves_stage_state` |
| FR-6.8 | Consent gate | `test_job.py::test_consent_check_*`; `tests/integration/test_cli_commands.py::test_make_refuses_presenter_without_consent` |
| NFR-1 | Cross-platform orchestrator | `.github/workflows/ci.yml` matrix (ubuntu-latest, windows-latest) |
| NFR-2/3 | Performance / 4GB-safe | RT-3/RT-4 timings; `run_with_oom_retry` unit tests |
| NFR-4 | No redundant re-work | `tests/integration/test_compose_synthetic.py::test_compose_stage_is_idempotent_via_is_done` |
| NFR-5 | No unwanted network calls | Manual code audit; `docs/security/threat-model.md` |
| NFR-6 | GPU-free testability | `tests/e2e/test_smoke_e2e.py` (dummy engines) |
| NFR-7 | Logging / timing summary | `echoface/util/log.py`, `cli.py::_print_timing_table` (exercised by e2e test, not separately asserted on log content) |
| NFR-8 | Lint/type/coverage gates | `.github/workflows/ci.yml::lint` job |
| NFR-9 | Secret/PII hygiene | `.github/workflows/ci.yml::gitleaks` job, `.pre-commit-config.yaml` |
| NFR-10 | Consent enforced in code | Same as FR-6.8 |
