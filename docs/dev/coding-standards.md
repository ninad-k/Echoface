# Coding Standards

## Style
- Enforced by `ruff check`/`ruff format` (config in `pyproject.toml`
  `[tool.ruff]`) — don't hand-format against it; run the formatter.
- Rule set: `E, F, W, I, UP, B, SIM, C4` (pyflakes, pycodestyle, isort,
  pyupgrade, bugbear, simplify, comprehensions). `E501` (line length) is
  off — the formatter handles wrapping. `B008` is off for
  `echoface/cli.py` — `typer.Option(...)` as a default *is* the Typer API.
- Line length 110.

## Types
- Type-hint new code in `echoface/` (the orchestrator package). `mypy
  echoface` must stay clean (`pyproject.toml` `[tool.mypy]`).
- `scripts/*_runner.py` are intentionally excluded from mypy — they
  import optional heavy dependencies (torch, cv2, faster_whisper) that
  aren't installed in the orchestrator's type-check environment.

## Module layout conventions
- `echoface/stages/*.py`: one file per pipeline stage, each exposing pure
  functions (testable without a GPU) plus a `Stage` subclass that wires
  them into `inputs()`/`outputs()`/`run()`.
- `echoface/util/*.py`: no stage-specific logic; each module has a single
  clear responsibility (`ffmpeg.py`, `gpu.py`, `text.py`, `proc.py`,
  `env.py`, `log.py`).
- `scripts/*_runner.py`: the *only* place that imports vendor ML code.
  Keep vendor imports scoped inside functions (not module-level) where the
  import can reasonably fail (e.g. optional engines) so the file stays
  importable for reference/testing without the heavy venv.

## Testing conventions
- Every new pure function gets a unit test in `tests/unit/`.
- Every new CLI-visible behaviour or stage-to-stage handoff gets an
  integration test in `tests/integration/`.
- A real bug fix gets a named regression test (see `docs/qa/defect-log.md`
  for the pattern — the test's docstring should say what real bug it
  guards against).
- Mock subprocess/network calls in unit tests (see
  `tests/unit/test_gpu_util.py`, `tests/unit/test_face_stage.py`'s
  OOM-retry tests) rather than requiring real services.
- Tests that need ffmpeg check `ffmpeg_available()` and
  `pytest.mark.skipif` rather than failing hard when it's absent.

## Docstrings / comments
- Prefer explaining *why*, not *what* — the "what" should be clear from
  the code + type hints. See existing docstrings in `echoface/stages/`
  and `echoface/util/ffmpeg.py` for the house style: a short summary line,
  then the non-obvious reasoning (e.g. why a magic number was chosen, what
  real-world measurement justified it).
- Reference the ADR/defect-log entry when a piece of code exists *because*
  of a specific bug or decision (see `build_audio_premix_filtergraph`'s
  docstring for an example).

## Config changes
- New config keys: add to the relevant pydantic model in
  `echoface/config.py` with a sensible default (nothing should be
  *required* beyond what's already required), update
  `config/echoface.yaml` with a documented example, and update
  `docs/ops/configuration-reference.md`.
- Machine-specific/secret-shaped values go through
  `echoface/util/env.py`'s override mechanism, documented in
  `.env.example` — don't add a new bare `os.environ.get()` call elsewhere.
