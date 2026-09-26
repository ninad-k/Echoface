# Improvements and Known Issues

Prioritised (P0 = do soon, P2 = nice-to-have), written during the
publication/hardening pass. Items marked **Fixed in this pass** were
small and low-risk enough to address immediately rather than just log.

**Update (v0.2.0):** every P0/P1/P2 item below has now been worked
through — each is marked **Resolved in v0.2.0** (with how) or
**Deferred** (with why). See `CHANGELOG.md`'s `[0.2.0]` section and
ADR-0008/ADR-0009 for the two items significant enough to warrant their
own ADR.

## P0 — worth addressing soon

1. **Loudness tuning (-9 dBFS pre-limiter, -2.5 dBTP target) is
   calibrated against exactly two real renders.**
   **Resolved in v0.2.0.** Pre-limiter ceiling, TP target, spec
   tolerance, and max re-encode attempts are now config fields
   (`compose.pre_limiter_dbfs`, `compose.true_peak_dbtp`,
   `compose.loudness_tolerance_lu`, `compose.loudness_hard_tp_ceiling_dbtp`,
   `compose.loudness_max_encode_attempts`). `ComposeStage` measures the
   **actual final encoded file** (not just the pre-encode estimate) and,
   if it lands outside ±0.5 LU or above the TP ceiling, re-encodes once
   with corrected offsets before accepting. Verified against 4 synthetic
   profiles (quiet voice, hot voice, each with/without background music)
   in `tests/integration/test_compose_synthetic.py` and both real
   renders (`real-e2e-001`, `real-e2e-sadtalker`) — all landed within
   spec on the first attempt. See ADR-0009.
2. **CodeFormer restoration is not implemented.**
   **Resolved in v0.2.0.** Real implementation against the official
   sczhou/CodeFormer source and GitHub-release weights
   (`models/codeformer/codeformer.pth`, SHA256
   `1009e537e0c2a07d4cabce6355f53cb66767cd4b4297ec7a4a64ca4b8a5684b7`).
   `scripts/codeformer_runner.py` mirrors the vendor's own
   `inference_codeformer.py` logic and is wired into `FaceStage`
   (`face.restore: codeformer`). S-Lab License 1.0 (non-commercial)
   is documented in `models/MODELS.md`, `docs/security/license-matrix.md`,
   and `models/licenses.yaml` (flagged by `doctor`). Verified for real:
   direct-runner run on `output/real-e2e-001`'s face (552 frames,
   ~3m/552f, ffprobe + frame-extraction confirmed clean output), a
   mouth-region variant on a 2s clip, and a full orchestrator run
   (`clean --from face` + `resume --config config/real_e2e_codeformer.yaml`,
   198.5s total, final frame-extraction confirmed correct captions +
   restored face + open mouth with no artefacts).
3. **`echoface doctor`'s model-licence check is narrow.**
   **Resolved in v0.2.0.** `_check_monetization_licence` now reads a
   machine-readable licence table, `models/licenses.yaml` (loaded via
   the new `echoface/licenses.py`), and flags **every** active
   non-commercial model for the given config when `monetized: true` —
   Wav2Lip, XTTS (CPML), CodeFormer (S-Lab), plus `check`-status entries
   (S3FD, SadTalker/GFPGAN sub-checkpoints) — instead of the single
   hardcoded Wav2Lip case. Covered by `tests/unit/test_licenses.py`
   (7 tests, including a real-file smoke test against the shipped
   `models/licenses.yaml`).
4. **No automated real-GPU regression testing.**
   **Resolved in v0.2.0.** Added `tests/gpu/test_real_engines.py`
   (marked `gpu`/`ollama`/`slow`, excluded from default `pytest` runs,
   each test skips — not fails — when prerequisites are missing) covering
   real Wav2Lip, GFPGAN, CodeFormer (mouth-region), Piper, and Ollama
   script generation on tiny inputs. `scripts/run_gpu_tests.ps1` runs
   them locally; actually run for this pass: **5 passed in 63.49s**. A
   `workflow_dispatch`-only GitHub Actions workflow
   (`.github/workflows/gpu-tests.yml`, `runs-on: [self-hosted, gpu]`)
   lets a maintainer trigger the same suite against a self-hosted GPU
   runner without ever blocking normal CI; the workflow file documents
   how to register such a runner, since no runner was registered or any
   machine/GitHub setting changed as part of this pass (out of scope by
   explicit instruction).

## P1 — real but lower urgency

5. **`anchor1` sample presenter intentionally has no valid consent
   file**, a common first "why won't this render?" confusion.
   **Resolved in v0.2.0.** The consent-refusal error now prints a
   "what to do next" block pointing at `echoface presenter init <name>`,
   the no-GPU `smoketest` demo config, and the docs. The new
   `echoface presenter init <name>` command scaffolds
   `assets/portraits/<name>/{meta.yaml,README.md}` with a consent
   checklist — the scaffolded `consent_ref` deliberately points at a
   file that does not yet exist, so the consent gate still refuses until
   a real document is added (verified by
   `test_presenter_init_scaffolds_meta_yaml_without_weakening_consent_gate`).
6. **`echoface batch`'s happy path has no automated test.**
   **Resolved in v0.2.0.** Added `tests/e2e/test_batch.py`:
   `test_batch_happy_path_renders_every_topic` (2 topics, mocked
   `call_ollama`, asserts both produce `final.mp4`) and
   `test_batch_continues_past_a_single_job_failure` (first topic's
   script generation raises, batch continues, exits 0, only the
   surviving topic has `final.mp4`).
7. **No job retention/pruning.**
   **Resolved in v0.2.0.** New `echoface prune --older-than 30d
   --keep-final` command (`echoface/prune.py`), driven by
   `config.prune.{older_than,keep_final}` defaults. **Dry-run by
   default** — prints a table of candidates and total size; actual
   deletion requires the explicit `--delete` flag. `keep_final` removes
   only intermediate artefacts, preserving `final.mp4`/`metadata.json`/
   `job.json`. Covered by 13 unit tests (`tests/unit/test_prune.py`) plus
   2 CLI integration tests.
8. **Face-box cache doesn't dedupe across a ping-pong render's
   forward/reverse halves.**
   **Resolved in v0.2.0, with a caveat.** Added
   `fold_pingpong_index()` (`echoface/util/ffmpeg.py`) — a pure
   triangle-wave index-folding function, thoroughly unit tested
   (`tests/unit/test_ffmpeg_util.py`) — wired into
   `scripts/wav2lip_runner.py`'s `face_detect()` (new
   `--pingpong_original_frames` arg) so detection runs once per unique
   original frame and folded indices reuse the cached box, and into
   `Wav2LipEngine.render()` (`echoface/stages/face.py`) to compute and
   pass that argument when a ping-pong loop is used. **Caveat**: this
   specific wiring was code-reviewed and unit-tested at the pure-function
   level, but not independently re-verified end-to-end on a real
   ping-pong-triggering GPU render, because no committed real-face
   `idle.mp4` exists that's short enough to force the ping-pong path
   (the only real portrait fixture uses `source: photo`). Logged here
   rather than silently claimed as fully GPU-verified.
9. **GFPGAN restoration processes the whole detected face per frame**,
   not a mouth-only crop.
   **Resolved in v0.2.0.** Added `face.restore_region: face|mouth`
   (default `face`, preserving prior behaviour). `mouth` applies a
   feathered numpy mask (`echoface/util/restore_blend.py`,
   `mouth_region_mask()`/`blend_region()`, shared by both
   `scripts/gfpgan_runner.py` and `scripts/codeformer_runner.py`) so only
   the lower-face/mouth region is replaced by the restored pixels, with a
   smoothstep-feathered blend at the mask edge to avoid a visible seam.
   Verified for real on a 2s CodeFormer mouth-region clip (frame
   extraction confirmed a clean blend, forehead/hair unchanged). Unit
   tests: `tests/unit/test_restore_blend.py` (8 tests).
10. **mypy excludes `scripts/*_runner.py`.**
    **Resolved in v0.2.0.** The exclude list turned out to be
    unnecessary once `[tool.mypy] ignore_missing_imports = true` (already
    project-wide) was actually exercised: all five runner scripts
    (`wav2lip_runner.py`, `gfpgan_runner.py`, `sadtalker_runner.py`,
    `xtts_runner.py`, `codeformer_runner.py`) now type-check cleanly with
    no bespoke stubs needed, after removing several now-redundant
    `# type: ignore` comments and deleting a stray `gfpgan/` directory at
    the repo root (a namespace-package artefact left over from an earlier
    manual GFPGAN run with the wrong cwd, which was confusing mypy's
    module resolution). `pyproject.toml`'s `[tool.mypy] exclude` is now
    just `["vendor/"]`, and CI's lint job runs `mypy echoface scripts`.

## P2 — nice-to-have / roadmap-adjacent

11. **Deferred.** macOS/Linux support for the heavy-model stages. Out of
    scope for this pass (no non-Windows dev/test machine available); the
    orchestrator itself remains cross-platform, only the
    Wav2Lip/SadTalker/Piper/XTTS/CodeFormer setup docs and
    `scripts/setup_windows.ps1` are Windows-specific. Tracked for a
    future pass.
12. **Deferred.** Local web UI, B-roll insertion, auto-thumbnails,
    multilingual re-voicing — roadmap items, not "improvements to
    existing behaviour"; still tracked in `docs/pm/roadmap.md`, none
    started in this pass (out of scope: this pass targeted the
    known-issues backlog, not new product surface).
13. **Deferred.** `dependency-audit` (pip-audit) in CI stays
    informational (`|| true`). Still fine at hobbyist/single-maintainer
    scale; revisit if the project grows contributors.
14. **Deferred.** `doctor`'s ffmpeg-version check still only confirms
    ffmpeg exists, not a minimum version. Low value relative to effort
    (no known ffmpeg-version-specific bug has been hit); revisit if one
    is found.

## Fixed in the v0.1.0 pass (kept for history)

- **`ECHOFACE_DOCTOR_TIMEOUT_S`** — the Ollama-reachability/model-list
  probe's fixed 3s timeout occasionally false-negatived under system load
  (observed once during heavy real-engine testing). Now configurable via
  env var, default unchanged. (`echoface/doctor.py::_doctor_timeout`)
- **`zip()` without `strict=`** in `scripts/wav2lip_runner.py` (3 sites) —
  ruff `B905`; added `strict=True` since these lists are constructed to be
  equal length by design, so a length mismatch is exactly the kind of bug
  `strict=True` should surface rather than silently truncate.
- **Redundant manual loop counter** in `voice.py`'s `concat_with_pauses`
  (ruff `SIM113`) — simplified to reuse `enumerate()`'s own index, no
  behaviour change.
- **Two mypy errors** (an unreachable `list[str | None]` type issue in
  `doctor.py`'s ffmpeg-version check, and a variable-redefinition warning
  in `script.py`'s retry loop) — both were real (if minor) type-safety
  gaps, fixed rather than suppressed.

## Fixed in the v0.2.0 pass (bugs found while doing the above)

- **Config precedence was `env > CLI > yaml > default`**, which meant an
  ambient `.env` value silently beat an explicit `--flag` on the command
  line — surprising and backwards from user expectation. Flipped to
  `CLI > env > yaml > default`; see ADR-0008.
- **PowerShell script encoding bug**: `scripts/run_gpu_tests.ps1`
  originally used em-dash characters inside double-quoted strings, which
  Windows PowerShell 5.1 misread under the system ANSI codepage, breaking
  string/quote parsing several lines downstream with confusing
  "missing closing paren/brace" errors. Fixed by using plain hyphens and
  single-quoted strings.
- **Stray `gfpgan/` directory at the repo root** (186MB, a namespace-
  package artefact from an earlier manual run with the wrong working
  directory) was shadowing the real `gfpgan` package for mypy's module
  resolution. Removed; `.gitignore` already excludes it going forward.
- **`tests/e2e/test_batch.py` initial fixture mismatch**: used
  `script.engine: file` (no `--script-file` equivalent exists for
  `batch`), causing every topic to fail with no output at all. Fixed by
  adding `tests/fixtures/dummy_batch.yaml` (`script.engine: ollama`) and
  mocking `call_ollama`.

## Process note
This list was produced by a maintainer/reviewer pass during the v0.1.0
publication hardening work, cross-referencing the defect log
(`docs/qa/defect-log.md`), the ADRs' own "Consequences" sections (several
ADRs already flagged their own trade-offs — this list consolidates and
prioritises them), and a fresh read of `echoface/` for anything not yet
written down. The v0.2.0 pass revisited every item above end-to-end.
