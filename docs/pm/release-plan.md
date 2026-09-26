# Release Plan

## Versioning
Semantic versioning (`MAJOR.MINOR.PATCH`). Pre-1.0: breaking changes may
land in a MINOR bump. Current release: **0.1.0** (first public release,
M1–M8 complete).

## Release process
1. Ensure `main` is green on CI (`ci.yml`: lint, gitleaks, dependency
   audit, tests on ubuntu-latest + windows-latest).
2. Update `CHANGELOG.md` under a new `## [x.y.z] - YYYY-MM-DD` heading.
3. Bump `version` in `pyproject.toml` to match.
4. Tag: `git tag vX.Y.Z && git push origin vX.Y.Z`.
5. `release.yml` triggers automatically: re-runs tests, builds sdist +
   wheel, creates a GitHub Release with those artifacts and changelog
   notes extracted from `CHANGELOG.md`.
6. **Not published to PyPI** at this stage — see `release.yml`'s trailing
   comment block for how to enable that later via trusted publishing.

## Release channel
Single channel: tagged GitHub Releases from `main`. No pre-release/beta
channel yet at v0.1.0 scale.

## Definition of done for a release
- All CI jobs green on the tagged commit.
- `CHANGELOG.md` updated.
- No open Issue labelled `blocker`.
- `docs/qa/defect-log.md` has no open Sev-1/Sev-2 defect against the
  release's scope.

## Planned releases

| Version | Theme | Target |
|---|---|---|
| 0.1.0 | First public release: M1–M8 pipeline, docs, CI/CD | This publication |
| 0.2.0 (candidate) | CodeFormer restore engine; doctor timeout/robustness follow-ups; loudness re-tuning if real-world feedback shows drift | TBD, issue-driven |
| 1.0.0 (candidate) | API/CLI stability commitment; broader OS support for heavy stages | TBD, after sustained real-world use |

## Rollback
Releases are immutable tags with attached artifacts; a bad release is
addressed by publishing a new patch version, not by deleting/retagging.
