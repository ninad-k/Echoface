# Asset attribution

## Sample presenters (committed to this repo)

| Path | Origin | Licence / notes |
|---|---|---|
| `assets/portraits/anchor1/portrait.png` | Generated locally with `ffmpeg` (`color=c=0x4466aa`), a flat placeholder swatch — not a photo, not a face. | Original, CC0 / public domain equivalent. |
| `assets/portraits/anchor1/idle.mp4` | Generated locally with `ffmpeg` (`testsrc2` synthetic test pattern). | Original, CC0 / public domain equivalent. |
| `assets/portraits/smoketest/portrait.png` | Generated locally with `ffmpeg` (`color=c=0x336699`), a flat placeholder swatch. | Original, CC0 / public domain equivalent. |

These two placeholder presenters exist only so `echoface doctor` and the
pytest suite have something to point at; they contain no face and are
**not** meant to produce a good-looking render. `anchor1` additionally
ships with a `consent_ref` pointing at a file that does not exist, on
purpose, to exercise the consent gate (see `consent/README.md`).

## `realtest` presenter — NOT committed

`assets/portraits/realtest/portrait.png` (used only for local real-engine
verification, see `docs/qa/test-plan.md`) is `art_10.png` from
`vendor/SadTalker/examples/source_image/` — a demo asset bundled with the
[OpenTalker/SadTalker](https://github.com/OpenTalker/SadTalker) repository.
It appears to be a reproduction of a 19th-century academic-style oil
portrait (public-domain-era painting style), not a photograph of a real,
living, identifiable person.

**This repository does not commit that file.** SadTalker's `LICENSE`
covers its *code* under Apache-2.0 and does not make an explicit statement
about redistribution rights for the images under `examples/`, so — per
this project's policy of only committing assets we can clearly redistribute
— it stays out of version control. `scripts/setup_windows.ps1` copies it
from the freshly-cloned `vendor/SadTalker/examples/source_image/art_10.png`
into `assets/portraits/realtest/portrait.png` locally after cloning, so the
`realtest` presenter works the same way for anyone who runs setup, without
the image itself living in this repo's git history.

If you fork or redistribute this repository and want a `realtest`-style
presenter of your own, either let setup copy SadTalker's asset for you
locally (not into your fork's git history) or substitute your own
consented/licensed portrait.

## Consent fixtures

`consent/realtest_2026-09.txt` and `tests/fixtures/consent_smoketest.txt`
are **test fixtures**, not real consent documents — each file says so in
its own text. They exist only so the consent-gate check
(`echoface/job.py::check_presenter_consent`) has a file to find for the
`realtest`/`smoketest` presenters used in tests and local verification.
See `consent/README.md` for what a *real* consent document should contain.
