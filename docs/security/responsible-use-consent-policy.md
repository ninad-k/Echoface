# Responsible Use and Consent Policy

## Consent requirement
**Written consent is required before using any real person's face or
voice**, including family members. Store a short signed note (e.g.
`consent/wife_2026-09.pdf`) and reference it from the presenter's
`assets/portraits/<name>/meta.yaml` via `consent_ref`. A signed consent
note should state:
- The person's agreement to have their likeness/voice used to generate AI
  avatar videos.
- The intended use (e.g. "personal YouTube channel").
- The date, and their signature (physical or electronic).

## Technical enforcement
`echoface/job.py::check_presenter_consent` refuses to render a presenter
whose `meta.yaml` is missing, has no `consent_ref`, or whose referenced
file doesn't exist on disk — see ADR-0006 for the design rationale. This
is a **process safeguard**: it verifies a file exists at the referenced
path, not that the file is a genuine, adequate consent document for that
specific person. **Human judgement is still required** — the tool cannot
verify that the person named in the consent document is the person in the
portrait, or that the consent terms actually cover your intended use.

## Rules
- **No public figures, no impersonation.** Do not use celebrities,
  politicians, or anyone who hasn't agreed. Do not present the avatar as a
  real person saying things they never said.
- **Voice cloning follows the same rule.** Clone only your own voice or a
  voice with written permission (`voice.xtts_speaker_wav` — the config
  comment itself says "only with written voice consent"). Stock Piper
  voices avoid this entirely (they're not clones of a real, identifiable
  person's voice).
- **Check model licences before monetising** — see
  `docs/security/license-matrix.md`. Some lip-sync weights (notably the
  default Wav2Lip GAN checkpoint) are research/non-commercial only.

## Disclosure
See `docs/security/ai-disclosure-policy.md`.

## Sample/test assets
The presenters shipped with this repo for testing (`anchor1`,
`smoketest`) are synthetic placeholders (generated colour swatches/test
patterns) — not real people, no consent subject exists. The `realtest`
presenter (used only for local real-engine verification, not committed —
see `assets/ATTRIBUTION.md`) is a public-domain-era painting reproduction,
also not a real living person. Every consent-fixture file used in the
automated test suite says explicitly, in its own text, that it is a test
fixture and not a real consent document — do not use them as a template
for an actual consent document.

## If you're building on Echoface
If you extend or fork this project, keep the consent gate. Removing or
bypassing it (e.g. hardcoding a bypass, or building a UI that skips the
check) defeats the entire responsible-use design of this tool.
