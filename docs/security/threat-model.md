# Threat Model

Echoface is a local, offline CLI. This is a lightweight STRIDE-flavoured
pass over realistic risks, not a formal enterprise threat model — scoped
to what actually applies to a single-user local tool.

## Assets
1. The presenter's likeness/voice (face image/video, cloned voice).
2. The creator's generated scripts/videos before publication.
3. Local credentials/tokens the environment may hold (`HF_TOKEN`, if set).
4. The integrity of the rendered output (viewers trust it's disclosed as
   AI-generated).

## Trust boundaries
- **Local machine boundary**: everything runs as the invoking user's own
  process. No privilege escalation, no other user's data involved.
- **Ollama boundary**: a local HTTP server (`localhost:11434` by default).
  Only the topic string (and script-generation prompts) crosses this
  boundary — never face/voice media.
- **Hugging Face Hub boundary**: outbound HTTPS, one-time model weight
  downloads. No user data is sent; only a model identifier is requested.
- **Subprocess boundary**: the orchestrator invokes other Python
  interpreters and ffmpeg as subprocesses with config-derived arguments.

## Threats and mitigations

| # | Threat (STRIDE) | Scenario | Mitigation |
|---|---|---|---|
| T1 | Tampering | A malicious/corrupted model checkpoint (`.pth`) executes arbitrary code via `torch.load`'s pickle deserialization | Every checkpoint Echoface documents is from an official source (repo README/GitHub release/HF org) with a recorded SHA256 (`models/MODELS.md`); `SECURITY.md` explicitly warns against pointing config at untrusted checkpoints |
| T2 | Tampering | A malicious presenter's `meta.yaml`/portrait crafted to exploit the face-detection/render pipeline | Out of scope for this threat model in practice (same trust level as the invoking user); the consent gate is a *policy* control, not a sandboxing one |
| T3 | Information disclosure | A generated script or render accidentally reveals something the creator didn't intend (LLM output isn't perfectly controllable) | Creator reviews output before publishing (same expectation as any AI-generated content); no auto-publish step exists |
| T4 | Information disclosure | Secrets committed to the public repo (API keys, personal paths, real consent documents) | `gitleaks` in CI + pre-commit; `.gitignore` excludes `.env`/`output/`/`consent/` real documents; documented sensitive-data audit performed before first publish (see `docs/project/improvements-and-known-issues.md` for the audit record) |
| T5 | Denial of service | A very long/malformed topic or script causes runaway resource use | Word-count validation bounds script length; audio >40s is chunked rather than processed unbounded; no protection against a deliberately hostile *local* user, which is out of scope (single-user tool) |
| T6 | Elevation of privilege | N/A — no privilege boundary crossed; the tool never runs with elevated rights and doesn't need to |
| T7 | Spoofing | Output video could be mistaken for a real recording of a real person | Mitigated by the AI-disclosure line always appended to `metadata.json` (FR-5.5) and the consent-gate requirement (FR-6.8) — but this is a *labelling* control, not a technical watermark; a determined bad actor could strip the disclosure before uploading elsewhere. See `docs/security/ai-disclosure-policy.md` |
| T8 | Repudiation | A rendered video's provenance (which config/models produced it) is unclear later | `job.json` and `metadata.json` record the config hash, presenter, and disclosure line per render; `models/MODELS.md` records exact model versions/checksums used at setup time |
| T9 | Elevation of privilege | `.github/workflows/gpu-tests.yml` targets a self-hosted runner (needed for real GPU inference, which no GitHub-hosted runner provides) on a **public** repo — a self-hosted runner executes with the registering user's own OS-level permissions and network access, a meaningfully higher-stakes surface than GitHub's ephemeral hosted runners | Layered controls, all documented in `docs/ops/self-hosted-gpu-runner.md`: (1) fork PR approval is set to require approval for all outside contributors, so an unapproved fork PR can't trigger anything; (2) `gpu-tests.yml` is `workflow_dispatch`-only — never `push`/`pull_request` — so nothing runs without a maintainer explicitly triggering it; (3) `if: github.repository == 'ninad-k/Echoface'` on the job; (4) a CI lint step (`scripts/check_no_self_hosted_workflows.py`) fails the build if `ci.yml`/`release.yml` (which DO trigger on every push/PR) ever target a self-hosted runner; (5) the runner is on-demand via `scripts/gpu_runner.ps1 start`, not an always-listening service — stopped with Ctrl+C between test sessions; (6) registration/removal tokens are fetched fresh per use via `gh api`, never written to disk or logged |

## Out of scope
- Multi-tenant/shared-hosting use (Echoface assumes a single local user).
- Network-facing deployment (Echoface has no server mode).
- Formal supply-chain attestation of every transitive PyPI dependency
  (mitigated at a basic level by `pip-audit` in CI and Dependabot).

## Reporting
See `SECURITY.md`.
