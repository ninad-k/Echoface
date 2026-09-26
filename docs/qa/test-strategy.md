# Test Strategy

## Test levels

| Level | Location | What it covers | Runs in CI? |
|---|---|---|---|
| Unit | `tests/unit/` | Pure functions and small classes: config hashing, text normalisation, script JSON validation, caption alignment/grouping, ffmpeg filtergraph/loudnorm string building, OOM-retry logic (subprocess mocked), consent checks, `doctor`'s timeout/report logic | Yes |
| Integration | `tests/integration/` | Config override precedence (env > CLI > yaml > default), CLI commands against the real `Job`/`job.json` machinery, the compose stage's real ffmpeg pipeline against synthetic media | Yes |
| End-to-end | `tests/e2e/` | Full `make`→`clean`→`resume` flow through the real CLI with `dummy` engines and the real ffmpeg compose stage | Yes (ffmpeg installed in CI) |
| Real-engine (manual) | Documented in `docs/qa/test-plan.md` | Real Wav2Lip/SadTalker/GFPGAN/Piper/XTTS/faster-whisper on GPU hardware | No — no GPU on hosted runners (see ADR-0007) |

## Markers
`pyproject.toml` defines `gpu`, `ollama`, `slow` markers, excluded by
default (`addopts = "-m 'not gpu and not ollama'"`). No test currently
uses them — reserved for future tests that need real hardware/services,
so contributors can add such tests without breaking default CI/local
runs; they'd be run explicitly with `pytest -m gpu`.

## Test data
Synthetic only: ffmpeg-generated test patterns/tones
(`tests/integration/test_compose_synthetic.py`), a public-domain-painting
placeholder presenter for CI-safe local checks
(`assets/portraits/smoketest/`, `anchor1/`), and text fixtures under
`tests/fixtures/`. No real consent documents or real people's media are
used anywhere in the test suite.

## Coverage policy
`pytest-cov`, branch-aware, target ≥80% on the orchestrator package
(`pyproject.toml` `[tool.coverage]`). Measured at 80% overall at v0.1.0;
modules dominated by real-subprocess/GPU code (`stages/face.py`,
`stages/voice.py`'s real-engine paths) are lower and accepted as such —
see `docs/qa/test-plan.md` for what covers those paths instead (manual
real-engine verification, and unit tests of the *logic around* the
subprocess call — OOM retry, box cache, engine selection).

## Regression policy
Every real bug found during development got a named regression test
before being considered fixed — see `docs/qa/defect-log.md` for the list
and the corresponding test in `tests/`.

## CI gate
`.github/workflows/ci.yml` runs lint (ruff, mypy), `gitleaks`, `pip-audit`
(informational), and the full unit+integration+e2e suite with coverage on
both `ubuntu-latest` and `windows-latest`, Python 3.14. A release tag
additionally re-runs the full suite before building artifacts
(`release.yml`).
