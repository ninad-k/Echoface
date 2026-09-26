# ADR-0006: Consent gate enforced in code, not just documentation

## Status
Accepted.

## Context
Echoface can make a still photo or idle-loop video of a real person
appear to speak arbitrary text. The spec is explicit (Section 2) that
written consent is required before using any real person's face or voice.
A policy that lives only in a README is trivially ignored (accidentally
or otherwise).

## Decision
`echoface/job.py::check_presenter_consent(presenter)` is called at the top
of `run_pipeline()` (`cli.py`), before any stage executes. It requires
`assets/portraits/<presenter>/meta.yaml` to exist, contain a non-empty
`consent_ref`, and for the file at that path to exist on disk. Any failure
raises `ConsentError`, which the CLI turns into a printed error and exit
code 2 — no job stages run, no files are written beyond the job
directory's bookkeeping.

## Consequences
- **Positive**: the check is a hard, testable gate (
  `tests/unit/test_job.py::test_consent_check_*`,
  `tests/integration/test_cli_commands.py::test_make_refuses_presenter_without_consent`),
  not a suggestion. The shipped sample presenter `anchor1` deliberately
  references a `consent_ref` that doesn't exist, so the gate is exercised
  by default rather than only in a hypothetical.
- **Limitation, by design**: this is a *process* safeguard, not a
  cryptographic or content-verification one — it checks that a file
  exists at the referenced path, not that the file is a genuine, valid
  consent document for that specific presenter. See
  `docs/security/responsible-use-consent-policy.md` for what a human
  reviewer should still check.
- `doctor` also surfaces every presenter's consent status
  (`_check_presenters`) so it's visible before attempting a render, not
  just discovered as a runtime failure.
