# ADR-0008: Config precedence — CLI flag beats environment variable

## Status
Accepted. Supersedes part of v0.1.0's behaviour (env var beat CLI flag).

## Context
v0.1.0 shipped with precedence `env var > CLI flag > yaml > default` —
env vars were applied *last* in `load_config`, so a `.env`-sourced value
silently overrode an explicit `--config`/CLI-flag choice made on that
specific invocation. In practice this is backwards from what a user
expects: an explicit flag typed on the command line for *this run* is the
most specific, most deliberate signal available, and should win over a
`.env` file's ambient default that the user may have set up weeks earlier
and forgotten about. Discovered as a real point of confusion during the
v0.2.0 hardening pass — a user setting `ECHOFACE_OLLAMA_HOST` in `.env`
for one project, then passing a different `--config` pointing at a
different host for a one-off run, would have silently gotten the `.env`
host instead of the one their config file named.

## Decision
`echoface/config.py::load_config` now applies environment-variable
overrides (`_apply_env_overrides`) immediately after loading the YAML
file, and CLI overrides (the `overrides` dict, built from Typer options)
last. Final precedence: **CLI flag > environment variable (.env) > YAML
(`config/*.yaml`) > pydantic field default**.

## Consequences
- **Positive**: matches the principle of least surprise — the most
  specific/explicit input for a given run always wins. `.env` remains
  exactly what it's for: ambient, machine-level defaults (Ollama host,
  ffmpeg path, etc.) that apply unless something more specific is given.
- **Negative**: this is a breaking behaviour change from v0.1.0 for anyone
  relying on `.env` overriding a CLI flag (unlikely in practice, given
  `.env` support only shipped in v0.1.0 and CLI flags for the affected
  keys — `--config` primarily — were always the more common path).
  Documented in `CHANGELOG.md`'s 0.2.0 section.
- Regression test:
  `tests/integration/test_config_precedence.py::test_precedence_cli_override_beats_env_var`.
