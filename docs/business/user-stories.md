# User Stories

Format: `As a <role>, I want <capability>, so that <benefit>.` Acceptance
criteria reference the requirement IDs in `docs/business/srs.md`.

## US-1: Generate a Short from a topic

As a **solo content creator**, I want to run one command with just a
topic, so that I get a publish-ready vertical video without manually
scripting, recording, or editing.

- **AC1**: `echoface make --topic "<topic>"` exits 0 and produces
  `output/<job-id>/final.mp4` and `metadata.json`. (FR-6.1, FR-5.1)
- **AC2**: `final.mp4` is 1080x1920, H.264/AAC. (FR-5.1)
- **AC3**: `metadata.json`'s description contains the AI-disclosure line.
  (FR-5.5)

## US-2: Supply my own script

As a **creator who already writes scripts**, I want to skip the LLM and
provide my own text, so that I control the exact wording while still
getting voice/face/captions/compose automated.

- **AC1**: `echoface make --script-file my_script.txt` produces the same
  artifacts as topic-based generation, without calling Ollama. (FR-1.5)

## US-3: Resume an interrupted render

As a **creator on a laptop that might sleep/lose power mid-render**, I
want to resume a job without redoing completed stages, so that I don't
waste GPU time re-running a 2-minute face render that already succeeded.

- **AC1**: `echoface resume <job-id>` skips any stage whose config hash
  matches the recorded one and whose output files still exist. (FR-6.3,
  NFR-4)
- **AC2**: Re-running `make` with the same `--job-id` behaves the same
  way (doesn't silently wipe progress). (FR-6.7)

## US-4: Re-render just the ending

As a **creator who wants a different call-to-action**, I want to
invalidate only the caption/compose stages and re-run, so that I don't
have to regenerate the voice and lip-synced video.

- **AC1**: `echoface clean <job-id> --from captions` resets captions and
  compose to pending and deletes their output files, leaving
  script/voice/face untouched. (FR-6.4)

## US-5: Be stopped from rendering someone without consent

As a **responsible creator**, I want the tool to refuse to render a
presenter I haven't recorded consent for, so that I can't accidentally
ship a deepfake of someone who didn't agree.

- **AC1**: `echoface make --presenter <name>` exits with a clear error
  (exit code 2) if `assets/portraits/<name>/meta.yaml` has no
  `consent_ref`, or the referenced file doesn't exist. (FR-6.8, NFR-10)

## US-6: Know my setup is ready before rendering

As a **new user setting up on a fresh machine**, I want a single command
that tells me what's missing (GPU, ffmpeg, Ollama, model files, venvs), so
that I don't discover problems mid-render.

- **AC1**: `echoface doctor` exits without crashing regardless of what's
  missing, and prints a red/green table per check. (FR-6.5)
- **AC2**: It warns (doesn't silently allow) if a non-commercial model is
  selected while `monetized: true`. (BR-3 in the BRD)

## US-7: Get accurate captions even with mispronounced/technical words

As a **creator whose script has names or jargon Whisper might mishear**,
I want captions to show the script's actual spelling, so that viewers
don't see garbled text.

- **AC1**: Recognised words are aligned to the canonical script text via
  difflib and the script's spelling wins where they match. (FR-4.2)

## US-8: Batch-render a week of Shorts overnight

As a **creator planning a week of content**, I want to queue several
topics and let them render unattended, so that I wake up to a folder of
finished videos.

- **AC1**: `echoface batch --file topics.txt` renders one job per line and
  continues past an individual job's failure rather than aborting the
  whole batch. (FR-6.2)

## US-9: Trust the loudness is broadcast-safe

As a **creator uploading to platforms with loudness normalisation
(YouTube, TikTok)**, I want my video's audio to land at a standard
loudness without clipping, so that it doesn't get auto-turned-down or
sound distorted.

- **AC1**: Final integrated loudness measures within ±0.5 LU of the
  configured target (default -14 LUFS). (FR-5.4)
- **AC2**: Final true peak measures ≤ -1 dBTP. (FR-5.4)

## US-10: Test the whole pipeline without a GPU

As a **contributor without a GPU**, I want to exercise the full pipeline
shape in CI, so that I can verify my changes don't break stage handoffs
without needing real hardware.

- **AC1**: Setting all three heavy-stage engines to `dummy` runs the full
  pipeline using only ffmpeg, producing a valid `final.mp4`. (NFR-6)
