# Stakeholders and RACI

## Stakeholders

| Stakeholder | Interest |
|---|---|
| Maintainer (@ninad-k) | Owns roadmap, code quality, releases; primary user |
| End users / creators | Run the CLI to produce videos; report issues, request features |
| Contributors | Submit PRs; expect a documented, testable codebase (`CONTRIBUTING.md`) |
| Presenters (consent subjects) | The real people whose face/voice may be used — protected by the consent gate, never a direct user of the tool |
| Upstream model authors (Rudrabha/Wav2Lip, OpenTalker/SadTalker, TencentARC/GFPGAN, rhasspy/Piper, Systran/faster-whisper, Coqui/XTTS) | Licence terms bind how their models may be used; attribution owed in `models/MODELS.md` |
| Platform policies (YouTube/TikTok/Instagram) | Require synthetic-content disclosure; Echoface bakes a disclosure line into every render's metadata |

## RACI (roles: **R**esponsible, **A**ccountable, **C**onsulted, **I**nformed)

Single-maintainer project today — RACI is mostly R=A=Maintainer, recorded
here for when contributors join.

| Activity | Maintainer | Contributor | End user |
|---|---|---|---|
| Roadmap / scope decisions | R, A | C | I |
| Code review / merge | R, A | R (submits) | I |
| Release cut / tagging | R, A | I | I |
| Security report triage | R, A | C | R (reports) |
| Documentation accuracy | R, A | C | I |
| Model licence compliance | R, A | C | R (must check before monetising) |
| CI/CD pipeline maintenance | R, A | C | I |
| Consent policy enforcement (code-level) | R, A | — | R (must supply real consent docs for their own presenters) |
