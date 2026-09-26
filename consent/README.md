# Consent documents

Put signed, written consent for every real person whose face and/or voice is
used by Echoface here, e.g.:

```
consent/anchor1_2026-09.pdf
consent/wife_2026-09.pdf
```

Each file should be a short signed note (scan or PDF) stating that the
person agrees to have their likeness/voice used to generate AI avatar
videos, the intended use (e.g. "personal YouTube channel"), and the date.

Reference the file's path from the presenter's `assets/portraits/<name>/meta.yaml`
via the `consent_ref` field. Echoface refuses to render a presenter whose
`consent_ref` is missing or whose target file does not exist on disk — see
`echoface doctor` and the consent check in `echoface/job.py`.

Do not commit real consent documents to a shared/public git repository.
This folder is intentionally empty (aside from this note) in the sample
project — the sample presenter `anchor1` references
`consent/anchor1_2026-09.pdf`, which does not exist, on purpose, so that the
consent gate can be demonstrated and tested.
