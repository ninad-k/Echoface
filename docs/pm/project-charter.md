# Project Charter

## Project name
Echoface — local AI avatar video pipeline

## Purpose
See `docs/business/brd.md` for the full business need. In short: give a
solo creator a free, fully local, offline replacement for paid avatar
video services, from topic to a publish-ready 9:16 Short.

## Objectives
1. Ship a working M1–M8 pipeline (script → voice → face → captions →
   compose) runnable end-to-end with a single command.
2. Keep it usable on modest consumer hardware (4 GB VRAM target, verified
   on 8 GB).
3. Bake in consent and disclosure as hard requirements, not documentation.

## Scope
See `docs/business/brd.md` §3 for in/out-of-scope detail.

## Success criteria

| Criterion | Target | Status (v0.1.0) |
|---|---|---|
| `echoface make --topic ...` produces a valid final.mp4 | 1080x1920, h264/aac | Met — verified real render |
| Runs within loudness spec | -14 LUFS ±0.5, ≤ -1 dBTP | Met — measured -14.09/-13.95 LUFS, -2.22/-1.69 dBTP on two real renders |
| Consent gate blocks unconsented presenters | Hard refusal, tested | Met |
| Test suite passes, decent coverage | ≥80% on pure-logic modules | Met — 80% overall, 105+ tests |
| CI green on Windows + Ubuntu | Both runners pass | Tracked in `docs/pm/raid-log.md` until first CI run confirms |
| Both face engines work for real | Wav2Lip + SadTalker verified on GPU | Met |

## Milestones
See `docs/pm/roadmap.md`.

## Budget / resources
No monetary budget — this is a personal open-source project. "Resources"
are the maintainer's time and one Windows machine with an NVIDIA GPU for
real-engine verification; CI runs on GitHub-hosted free-tier runners.

## Constraints and assumptions
See `docs/pm/raid-log.md`.

## Sponsor / owner
@ninad-k (repository owner, sole maintainer at v0.1.0).

## Authorization
This charter reflects a project already built through M1–M8 and prepared
for public release; it documents intent and scope retroactively as part
of the SDLC documentation pass, per the maintainer's request.
