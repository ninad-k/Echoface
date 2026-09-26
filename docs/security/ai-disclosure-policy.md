# AI Disclosure Policy

## Why
Major platforms (YouTube, and increasingly others) require creators to
disclose realistic altered or synthetic content. Beyond the platform
requirement, disclosing AI-generated presenters is simply honest
communication with viewers.

## What Echoface does automatically
Every render's `metadata.json` description has the configured
`compose.disclosure_line` (default: `"Presenter is AI-generated."`)
appended, unconditionally — this is not optional per-render, only the
*wording* is configurable (`compose.disclosure_line` in
`config/*.yaml`). See `ComposeStage._write_metadata`
(`echoface/stages/compose.py`) and FR-5.5 in `docs/business/srs.md`.

## What Echoface does NOT do (human steps still required)
- **Tick the platform's synthetic-content disclosure toggle at upload.**
  Echoface has no upload integration (see `docs/pm/roadmap.md` for the
  "auto-upload" roadmap idea) — this remains a manual step for every
  platform you publish to.
- **Embed a visible on-screen watermark.** The disclosure lives in the
  video's *metadata* (title/description field), not burned into the
  video frames. A viewer who only sees the video (not its description) on
  a platform that strips/hides descriptions may not see the disclosure.
  Consider this a known limitation, not a guarantee — see
  `docs/project/improvements-and-known-issues.md`.
- **Prevent removal.** Nothing stops a user of this tool from deleting the
  disclosure line before uploading. This is a labelling default, not a
  cryptographic/tamper-evident watermark (see `docs/security/threat-model.md`
  T7).

## Recommended practice
1. Keep the default `disclosure_line` unless your platform requires
   specific wording.
2. At upload, tick the platform's own "altered or synthetic content"
   toggle if one exists.
3. Keep the disclosure text in the visible description, not just alt text
   or metadata that viewers won't see.
