# Security Policy

## Reporting a vulnerability

Please report security issues privately via **GitHub Security Advisories**
(this repo's "Security" tab → "Report a vulnerability") rather than a
public issue. If that isn't available, open an issue titled vaguely
(no exploit detail) and ask for a private contact.

We aim to acknowledge reports within 5 business days. This is a personal,
part-time-maintained project — there is no paid bug bounty.

## Supported versions

Echoface is pre-1.0 (`0.1.0`). Only the latest commit on `main` is
supported; there are no maintained release branches yet.

## Scope and threat model

Echoface is a **local, offline CLI tool** you run on your own machine. It
is not a network service — it doesn't listen on a port, doesn't accept
untrusted network input by default, and doesn't handle other people's
data. See `docs/security/threat-model.md` for the full breakdown. In
short, the realistic risk surface is:

- **Untrusted model checkpoints**: `.pth`/`.pt`/`.ckpt` files can contain
  arbitrary pickled Python objects that execute code on load
  (`torch.load`). Echoface's own downloads (documented with SHA256 and
  source in `models/MODELS.md`) come from each project's official
  README/GitHub-release/HF-org links, never third-party mirrors. **Do not
  point `face.engine`/`voice.engine` config at a checkpoint you don't
  trust the source of.**
- **Local subprocess execution**: the face/voice stages shell out to
  Python interpreters in `envs\face`/`envs\tts` running scripts under
  `scripts/`. These paths are config-driven (`voice.piper_exe`,
  `face.engine`, etc.) — don't point them at untrusted executables.
- **Ollama / local LLM output**: the script stage's JSON is schema- and
  word-count-validated (`echoface/stages/script.py`) before use, but it is
  still model output — review generated scripts before publishing, same as
  you would any AI-generated text.
- **Consent gate**: `echoface/job.py::check_presenter_consent` refuses to
  render a presenter without a `consent_ref` pointing at an existing file.
  This is a *process* safeguard (reminds you to have consent on file), not
  a cryptographic one — it does not verify the consent document's content.

## Secrets

Echoface does not require any secret to run its default (local) stack —
no API keys, no cloud credentials. A few *optional* values (documented in
`.env.example`) can be set via a local, gitignored `.env` file: an
optional `HF_TOKEN` for gated Hugging Face models, and non-secret
machine-path overrides (Ollama host, ffmpeg path). **Never commit `.env`**
— it's gitignored; `.env.example` (placeholders only) is the committed
template. `gitleaks` runs in CI and as a pre-commit hook on every change.

## Dependencies

Dependabot (`.github/dependabot.yml`) keeps `pip` and GitHub Actions
dependencies current. CI runs `pip-audit` on every push/PR (see
`.github/workflows/ci.yml`) to flag known-vulnerable dependency versions.
