# Business Requirements Document (BRD)

Status: reflects the implementation as of v0.1.0 (M1–M8 complete). Source
of truth for *why* Echoface exists; see `docs/business/srs.md` for *what*
it must do and `docs/architecture/software-architecture.md` for *how*.

## 1. Business need

Paid AI-avatar video services (HeyGen, Synthesia, and similar) charge
per-minute or per-seat subscription fees, require uploading a presenter's
likeness and voice to a third-party cloud, and cap output. For a creator
who wants to publish short-form talking-head video regularly (YouTube
Shorts, Reels, TikTok) without recurring cost, without sending a face/voice
to a vendor, and without a usage ceiling, no adequate free/local
alternative existed that combined script generation, voice synthesis,
lip-sync, captioning and final video assembly into one tool.

## 2. Business objectives

| ID | Objective | Success measure |
|----|---|---|
| BO-1 | Eliminate per-minute/subscription cost for avatar video generation | $0 marginal cost per video after one-time model downloads |
| BO-2 | Keep all presenter likeness/voice data on the creator's own machine | No stage in the pipeline makes a network call carrying user media (verified: script stage is the only stage that calls a network service, and it sends only the topic string to a *local* Ollama server) |
| BO-3 | Produce a publish-ready vertical short from a single command | `echoface make --topic "..."` yields `final.mp4` + `metadata.json` in one run |
| BO-4 | Run on modest consumer hardware | Design target 4 GB VRAM / 16 GB RAM (spec); verified working on an 8 GB RTX 5070 Laptop |
| BO-5 | Avoid enabling non-consensual deepfakes | Hard technical gate refusing to render without an on-file consent reference (`docs/security/responsible-use-consent-policy.md`) |

## 3. Scope

**In scope (delivered, v0.1.0):** topic-to-script generation via a local
LLM (Ollama); text-to-speech via Piper (default) or XTTS v2 (optional,
non-commercial licence); lip-synced talking-head video via Wav2Lip
(default) or SadTalker (optional, more head motion); optional GFPGAN face
restoration; word-level captions via faster-whisper; final 1080x1920
assembly with background, burned-in captions, music ducking and two-pass
loudness normalisation; a CLI (`make`, `batch`, `resume`, `clean`,
`doctor`); per-job resumability; a per-presenter consent gate.

**Out of scope (see `docs/pm/roadmap.md` for candidates):** a GUI; cloud
deployment/hosting; automatic upload to YouTube/TikTok; multi-language
translation/dubbing; B-roll insertion; thumbnail generation; billing or
multi-tenant use (this is a single-user local CLI).

## 4. Stakeholders

See `docs/pm/stakeholders-raci.md`.

## 5. Business rules

- BR-1: A presenter must not be rendered without a `consent_ref` pointing
  at an existing file (`echoface/job.py::check_presenter_consent`).
- BR-2: Every rendered video's `metadata.json` description must contain
  the configured AI-disclosure line (default: "Presenter is AI-generated.").
- BR-3: `echoface doctor` must warn (not silently proceed) when a
  monetisation-incompatible model (e.g. the default Wav2Lip GAN checkpoint,
  research/non-commercial licensed) is selected while `monetized: true`.

## 6. Assumptions and constraints

See `docs/pm/raid-log.md` (Assumptions and Constraints sections) — e.g.
Windows 11 is the only currently-supported OS for the heavy-model stages;
CI validates orchestrator logic cross-platform but not GPU inference.

## 7. Cost-benefit summary

One-time cost: model downloads (~2–4 GB depending on engines chosen) and
setup time (`scripts/setup_windows.ps1`). Ongoing cost: electricity for
local compute; render time (2–5 minutes per ~20s Short on the reference
hardware, see `docs/ops/performance-vram-guide.md`). Benefit: unlimited
renders at $0 marginal cost, full data locality, no vendor lock-in.
