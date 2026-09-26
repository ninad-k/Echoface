# ADR-0004: Two-pass loudnorm (measure, then apply linearly)

## Status
Accepted.

## Context
The spec requires final audio at -14 LUFS integrated loudness. ffmpeg's
`loudnorm` filter has two modes: single-pass ("dynamic", a real-time
gain-riding estimate, typically accurate to within a few LU) and two-pass
(`linear=true` with `measured_*`/`offset` values from a first
measurement pass, accurate to a fraction of an LU). A single-pass first
attempt measured -15.6 LUFS on a real render — over 1 LU off target.

## Decision
`ComposeStage` runs pass 1 (`build_audio_premix_filtergraph` + `loudnorm
print_format=json`, `-f null -`, no file written) using the *exact same*
voice+music mix filtergraph the real encode will use, parses the JSON,
then builds pass 2's filter string (`build_loudnorm_filter(..., measured=...)`)
and runs it inside the single real-encode ffmpeg invocation — the
"single filtergraph for video" architecture from the spec is preserved;
only the *audio* half runs twice (once cheaply for measurement, once for
real).

## Consequences
- **Positive**: measured -14.09 to -13.95 LUFS on two different real
  renders — within the ±0.5 LU tolerance, versus -15.6/-15.0 with
  single-pass.
- **Negative / follow-on decisions required**: getting *both* the LUFS
  target and the -1 dBTP true-peak ceiling within tolerance simultaneously
  needed two more empirical fixes, because echoface's own peak-normalised
  voice audio has a large crest factor, and AAC re-encoding measurably
  overshoots the pre-encode PCM's true peak:
  1. A fast `alimiter` (-9 dBFS ceiling, `level=disabled`) added to the
     premix graph before loudnorm, so the linear correction has headroom
     to reach -14 LUFS without clipping on an outlier transient.
  2. `compose.true_peak_dbtp` targets -2.5 dBTP on the pre-encode PCM
     (not -1.5), to leave margin for AAC's overshoot (observed up to
     +1.1 dB on a real render).
  These two numbers were tuned against two specific real renders and may
  need revisiting for very different audio content — tracked in
  `docs/project/improvements-and-known-issues.md`.
- Pass 1 adds a small amount of wall-clock time per render (a few seconds,
  since it's audio-only, no video encode) — acceptable given the accuracy
  gain.
