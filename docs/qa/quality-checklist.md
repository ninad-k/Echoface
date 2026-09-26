# Quality Checklist

## Before every commit (local)
- [ ] `ruff check echoface scripts tests` clean
- [ ] `ruff format --check echoface scripts tests` clean
- [ ] `mypy echoface` clean
- [ ] `pytest tests/unit tests/integration tests/e2e` all pass
- [ ] `gitleaks git --staged` (or the pre-commit hook) reports no leaks
- [ ] No file >5 MB staged; no `.pth`/`.onnx`/`.safetensors`/output/.env staged

## Before merging a PR
- [ ] CI green on both `ubuntu-latest` and `windows-latest`
- [ ] New/changed behaviour has a test (unit, integration, or e2e as
      appropriate — see `docs/qa/test-strategy.md`)
- [ ] Docs updated if a config key, CLI flag, or stage contract changed
      (`docs/ops/configuration-reference.md`, `README.md`)
- [ ] `CHANGELOG.md` has an `[Unreleased]` entry

## Before a release (see `docs/pm/release-plan.md` for the full process)
- [ ] `docs/qa/defect-log.md` has no open Sev-1/Sev-2 against this
      release's scope
- [ ] If a heavy stage changed: real-engine verification re-run per
      `docs/qa/test-plan.md`'s RT-# table, results recorded there
- [ ] `models/MODELS.md` up to date if a model/version changed
- [ ] Version bumped in `pyproject.toml`, tag matches

## Good-Short quality checklist (from the original spec, product-level)
- [ ] Hook lands in the first 2 seconds; no greeting/intro
- [ ] One idea per Short; 25-45 seconds; sentences under ~12 words
- [ ] Captions always on, large, high contrast, 2-3 words at a time
- [ ] Source portrait: front-facing, even lighting, neutral closed mouth,
      ≥1024px, no hair/hands over the mouth
- [ ] Disclosure ticked at upload; description includes the AI line
      (automatic via `metadata.json`, still a human upload-time step)
