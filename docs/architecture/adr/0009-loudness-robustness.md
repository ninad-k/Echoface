# ADR-0009: Loudness self-verification and one-shot corrective re-encode

## Status
Accepted. Extends ADR-0004.

## Context
ADR-0004's two-pass `loudnorm` (tuned `-9 dBFS` pre-limiter, `-2.5 dBTP`
pre-encode target) hit spec on the two real renders it was tuned against.
But those constants were hand-picked against specific audio, and the
improvements review flagged this as a real robustness gap: different
voice content (quieter source, a different TTS engine, heavy background
music) has a different crest factor and could land outside `-14 LUFS
+/-0.5` or above `-1 dBTP` without anyone noticing, since the pipeline
never checked its own output.

## Decision
`ComposeConfig` gains explicit, tunable fields: `pre_limiter_dbfs`
(was a hardcoded default deep in `build_audio_premix_filtergraph`),
`loudness_tolerance_lu`, `loudness_hard_tp_ceiling_dbtp` (the actual
final-file spec, `-1.0` dBTP, distinct from `true_peak_dbtp`'s more
conservative *pre-encode* target), and `loudness_max_encode_attempts`
(default 2).

`ComposeStage.run()` now, after every encode, measures the **actual
final.mp4's audio track** (`_measure_final_file_loudness`, single-pass
`loudnorm print_format=json` against the real AAC output — not the
pre-encode PCM pass-1 measurement, which can't see codec overshoot). If
the measured integrated loudness is outside `loudness_tolerance_lu` of
the target, or true peak exceeds `loudness_hard_tp_ceiling_dbtp`, it
computes a correction (an additive offset to close the LUFS gap, and a
tightened pre-encode TP margin proportional to how far over the ceiling
it was) and re-encodes once. This repeats up to
`loudness_max_encode_attempts` times; if still out of spec at the last
attempt, it logs a warning (naming this ADR) and keeps the last encode
rather than looping indefinitely on adversarial input.

## Consequences
- **Positive**: verified for real across four different synthetic audio
  profiles (quiet voice, hot/peak-normalised voice, each with and without
  a music bed — `tests/integration/test_compose_synthetic.py::test_compose_stage_hits_loudness_spec_on_varied_audio_profiles`)
  plus both real Wav2Lip and SadTalker renders — every case landed within
  ~0.1 LU of -14 LUFS and comfortably under -1 dBTP, on the *first*
  attempt in all cases tested so far (the corrective retry path exists and
  is exercised by construction/logic, though no test profile so far has
  actually needed a second attempt — see the test file for exact
  numbers).
- **Negative**: worst case, a render now costs one extra full ffmpeg
  video re-encode (a few seconds to tens of seconds depending on length) —
  accepted, since correctness on the loudness spec matters more than
  saving that time, and it only triggers when actually needed.
- `metadata.json` now records both `loudness_measured_pass1` (pre-encode
  PCM estimate) and `loudness_measured_final` (the real, final,
  post-encode number that matters) for transparency.
