# Contributing to Echoface

Thanks for considering a contribution. This is a personal, part-time
maintained project — please be patient with review turnaround.

## Dev setup

```powershell
git clone https://github.com/ninad-k/Echoface.git
cd Echoface
py -3.14 -m venv .venv
.venv\Scripts\pip install -e ".[dev,captions]"
.venv\Scripts\pre-commit install   # optional but recommended
.venv\Scripts\pytest
```

You do **not** need a GPU, Ollama, or the heavy `envs\face`/`envs\tts`
venvs to contribute to the orchestrator — `tests/unit`, `tests/integration`
and `tests/e2e` all run with `dummy` engines and pure ffmpeg. See
`docs/architecture/adr/0007-dummy-engines.md` for why. If you're changing
a real engine (`scripts/*_runner.py`), see
`scripts/setup_windows.ps1` and `docs/ops/installation-deployment.md` for
the full GPU setup, and note real-engine changes can't be verified by CI
(no GPU on hosted runners) — describe your manual verification in the PR.

## Before opening a PR
```powershell
ruff check echoface scripts tests
ruff format --check echoface scripts tests
mypy echoface
pytest tests/unit tests/integration tests/e2e
```
All four must pass. `pre-commit run --all-files` runs the first three
plus `gitleaks` and basic hygiene checks in one command if you installed
the hook.

## Coding standards
See `docs/dev/coding-standards.md`.

## Adding a new stage or engine
See `docs/dev/adding-a-stage-or-engine.md` — the `Stage`/`FaceEngine`/
`VoiceEngine` interfaces are designed for exactly this.

## Commit messages
Logical, scoped commits preferred over one giant diff. No required format
beyond a clear one-line summary.

## Reporting bugs / requesting features
Use the issue templates (`.github/ISSUE_TEMPLATE/`). For security issues,
see `SECURITY.md` — please don't open a public issue with exploit detail.

## Code of Conduct
By participating, you agree to abide by `CODE_OF_CONDUCT.md`.

## Licence
By contributing, you agree your contribution is licensed under this
project's MIT licence (`LICENSE`).
