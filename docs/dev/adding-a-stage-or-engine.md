# How to add a new pipeline stage or a new engine for an existing stage

## Adding a new engine to an existing stage (common case)

Example: adding a new face engine (e.g. a future diffusion-based
talking-head model, see `docs/pm/roadmap.md`).

1. **Implement the engine class** in `echoface/stages/face.py`, subclassing
   `FaceEngine` and implementing
   `render(self, *, face_source, audio_path, out_path, cfg, logger=None)`.
   If it needs a GPU/heavy deps, write a `scripts/<name>_runner.py` that
   the engine's `render()` shells out to (see ADR-0002) — don't import
   heavy deps at the top of `face.py` itself.
2. **Register it** in `build_engine(cfg)`'s if/elif chain.
3. **Extend the config schema**: add the new value to `FaceConfig.engine`'s
   `field_validator` allowed set in `echoface/config.py`.
4. **Wire OOM retry** if it's GPU-based: call
   `run_with_oom_retry(build_cmd, initial_batch_size=..., device=..., ...)`
   from `render()`, same as `Wav2LipEngine`/`SadTalkerEngine`.
5. **Unit-test** the pure parts: `build_engine` returns the right class
   for the new config value (extend
   `tests/unit/test_face_stage.py::test_build_engine_returns_correct_class`),
   and any command-building logic (mock `run_with_oom_retry`, see
   `test_sadtalker_engine_passes_enhancer_flag_when_restore_gfpgan` for the
   pattern).
6. **Document**: add a row to `docs/ops/configuration-reference.md`'s
   `face.engine` options, and a licence entry to
   `docs/security/license-matrix.md` if it's a new model.
7. **Real-engine verification**: if it needs a GPU, this can't be CI-gated
   (ADR-0007) — run it manually per `docs/qa/test-plan.md`'s pattern and
   record the result there.

The same shape applies to `VoiceEngine` in `echoface/stages/voice.py`.

## Adding an entirely new pipeline stage

Less common — the current five stages (script/voice/face/captions/compose)
cover the spec. If you do need one:

1. Create `echoface/stages/<name>.py`, subclass `Stage`
   (`echoface/stages/base.py`) implementing `inputs()`, `outputs()`, and
   `run()`. Optionally override `extra_hash_inputs()` if the stage's
   idempotency should consider something beyond its config section (see
   `ScriptStage.extra_hash_inputs` for an example — it hashes the topic).
2. Add a config section to `EchofaceConfig` in `echoface/config.py` if the
   stage needs configuration, and make sure `stage_config(stage_name)`'s
   mapping includes it.
3. Insert it into `STAGE_ORDER` in `echoface/job.py` at the right point —
   this list drives both `clean --from`'s downstream-invalidation and the
   CLI's stage-execution order (`STAGE_CLASSES`/`_make_stage` in `cli.py`).
4. Add it to `STAGE_CLASSES` and `stage_outputs` (the file-deletion map for
   `clean`) in `echoface/cli.py`.
5. Write unit tests for the stage's pure logic, and update
   `tests/e2e/test_smoke_e2e.py` / `tests/fixtures/dummy.yaml` if the
   full-pipeline dummy-engine test needs to account for the new stage.
6. Update `docs/architecture/data-flow.md`'s diagram and the
   inputs/outputs table, and `docs/business/srs.md` with new FR IDs.
