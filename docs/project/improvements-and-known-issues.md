# Improvements and Known Issues

Prioritised (P0 = do soon, P2 = nice-to-have), written during the
publication/hardening pass. Items marked **Fixed in this pass** were
small and low-risk enough to address immediately rather than just log.

## P0 — worth addressing soon

1. **Loudness tuning (-9 dBFS pre-limiter, -2.5 dBTP target) is
   calibrated against exactly two real renders.** Both used Piper voice
   output with a similar crest factor. Different TTS engines (XTTS),
   music-heavy renders, or much longer scripts could land outside the
   ±0.5 LU / ≤-1 dBTP spec and need re-tuning. *Recommendation*: add an
   automated post-render assertion (fail loudly if measured loudness is
   out of spec) rather than trusting the static config values forever;
   track real-world reports.
2. **CodeFormer restoration is not implemented** — `face.restore:
   codeformer` is accepted by config validation but silently no-ops with
   only a log warning. Either implement it (mirroring
   `scripts/gfpgan_runner.py`'s pattern) or remove it from the accepted
   enum until it exists, so a typo/misconfiguration doesn't silently do
   nothing. *Recommendation*: remove from the schema or implement — leaving
   a documented-but-fake option is the worse of the two options.
3. **`echoface doctor`'s model-licence check is narrow.** It only flags
   Wav2Lip when `monetized: true`; it doesn't check XTTS's CPML licence,
   SadTalker's sub-model checkpoints, or GFPGAN's weight licence — all
   documented in `docs/security/license-matrix.md` but not
   programmatically enforced. *Recommendation*: generalise
   `_check_monetization_licence` to read a small licence table (could
   literally parse `models/MODELS.md`'s `commercial` column) instead of a
   single hardcoded case.
4. **No automated real-GPU regression testing.** Every real-engine
   verification (Wav2Lip, SadTalker, GFPGAN, Piper, XTTS, faster-whisper)
   was done manually and is not re-run automatically before a release —
   only documented as a checklist (`docs/qa/test-plan.md`). A regression
   in a future dependency bump (torch, opencv, etc.) wouldn't be caught
   until the next manual pass. *Recommendation*: if a self-hosted CI
   runner with a GPU ever becomes available, add a `gpu`-marked test tier.

## P1 — real but lower urgency

5. **`anchor1` sample presenter intentionally has no valid consent file**,
   which is correct for demonstrating the consent gate but is a common
   first "why won't this render?" confusion for new users. Documented in
   the user manual FAQ and troubleshooting, but a friendlier first-run
   experience (e.g. `doctor` suggesting `smoketest` or `realtest` instead
   for a first try) would help.
6. **`echoface batch`'s happy path has no automated test** — only its
   failure mode (missing file) is covered in
   `tests/integration/test_cli_commands.py`. The underlying per-topic loop
   reuses `run_pipeline`, which *is* well-tested, but the batch-specific
   continue-past-failure behaviour isn't directly asserted.
7. **No job retention/pruning.** `output/<job-id>/` accumulates
   indefinitely; nothing automatically cleans up old finished jobs. Fine
   at hobbyist scale, could surprise a heavy batch user on disk space.
8. **Face-box cache doesn't dedupe across a ping-pong render's
   forward/reverse halves** — it caches per (presenter, rendered frame
   count), so a forward-then-reverse loop still detects each unique
   original frame once per occurrence in the extended sequence rather
   than once total. A real but modest optimisation opportunity.
9. **GFPGAN restoration processes the whole detected face per frame**,
   not a mouth-only crop as a strict reading of the original spec
   ("GFPGAN on the face crop") might suggest. In practice this matches how
   GFPGAN is commonly used after Wav2Lip (including SadTalker's own
   `--enhancer gfpgan`) and looked correct in real renders, but a
   mouth-only crop would be faster and might reduce artefacts elsewhere
   in the frame.
10. **mypy excludes `scripts/*_runner.py`** (they import optional heavy
    deps not installed in the orchestrator's type-check env). A separate,
    minimal mypy pass using `envs\face`'s interpreter (or type stubs for
    torch/cv2) could close this gap, at real setup cost.

## P2 — nice-to-have / roadmap-adjacent

11. macOS/Linux support for the heavy-model stages (orchestrator is
    already cross-platform; Wav2Lip/SadTalker/Piper/XTTS install
    instructions are Windows-only).
12. A local web UI, B-roll insertion, auto-thumbnails, multilingual
    re-voicing — all tracked in `docs/pm/roadmap.md`, none started.
13. `dependency-audit` (pip-audit) in CI is informational (`|| true`) —
    doesn't gate merges. Fine at hobbyist scale; revisit if the project
    grows contributors.
14. `doctor`'s ffmpeg-version check trims to only the first output line;
    doesn't verify a *minimum* ffmpeg version, just that one exists.

## Fixed in this pass (not just logged)

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

## Process note
This list was produced by a maintainer/reviewer pass during the v0.1.0
publication hardening work, cross-referencing the defect log
(`docs/qa/defect-log.md`), the ADRs' own "Consequences" sections (several
ADRs already flagged their own trade-offs — this list consolidates and
prioritises them), and a fresh read of `echoface/` for anything not yet
written down.
