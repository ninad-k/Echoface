# ADR-0007: `dummy` engines for GPU-free testing

## Status
Accepted.

## Context
The pipeline's real engines (Wav2Lip/SadTalker, Piper/XTTS,
faster-whisper) need a GPU, multi-GB model downloads, and (for the script
stage) a running Ollama server — none of which a CI runner or a
contributor without a GPU has. Without *some* way to exercise the full
pipeline shape, stage-handoff bugs (wrong file paths, config plumbing,
filtergraph construction) would only surface on someone's GPU machine,
late.

## Decision
Every heavy stage has a `dummy` engine option selectable purely via config
(`voice.engine: dummy`, `face.engine: dummy`, `captions.engine: dummy`):
- Voice: generates a sine-wave tone of plausible duration via ffmpeg
  (`sine=frequency=220:duration=...`), no model.
- Face: loops the presenter's idle video or still image to the audio's
  duration via ffmpeg, no model.
- Captions: evenly distributes the known script words across the audio's
  measured duration (`generate_dummy_words`), no ML.

Combined with `--script-file` (bypassing the LLM), the entire pipeline —
including the *real* ffmpeg compose stage with its two-pass loudnorm and
ASS burn-in — runs end to end using only ffmpeg, verified in
`tests/e2e/test_smoke_e2e.py`.

## Consequences
- **Positive**: CI can genuinely exercise `make`, `clean`, `resume`, and
  the full stage-handoff chain, catching a wide class of bugs without a
  GPU. This is not a mock of the pipeline — it's the real orchestrator,
  real `Job`/`job.json` state, real ffmpeg compose, with only the
  heavy-model *inference* swapped out.
- **Negative**: dummy engines don't and can't catch bugs specific to real
  inference (e.g. an OOM-retry code path is unit-tested with a mocked
  subprocess, not exercised by the dummy engine, which never OOMs).
  Real-engine verification remains a manual, documented process on GPU
  hardware — see `docs/qa/test-plan.md`.
- Dummy output is not meant to look good (a sine tone, a looped static
  image) — it exists purely to validate pipeline *mechanics*.
