# Use Cases

## UC-1: Render a Short from a topic

- **Actor**: Creator (CLI user)
- **Preconditions**: `echoface doctor` reports no hard failures; presenter
  has a valid `consent_ref`; Ollama reachable with the configured model
  pulled (or `--script-file` used instead).
- **Main flow**:
  1. Creator runs `echoface make --topic "<topic>" --presenter <name>`.
  2. System creates a job folder `output/<YYYYMMDD-HHMM_slug>/`.
  3. System checks presenter consent; aborts (exit 2) if absent.
  4. Script stage generates and validates `script.json` (retry up to 3x on
     schema/word-count failure).
  5. Voice stage synthesises `voice.wav` + `voice_16k.wav`.
  6. Face stage unloads Ollama from VRAM, then renders `face.mp4`
     (looping/chunking/OOM-retry as needed), optionally restoring with
     GFPGAN.
  7. Captions stage transcribes and aligns words, writes `words.json` +
     `captions.ass`.
  8. Compose stage measures loudness (pass 1), builds the final
     filtergraph, encodes `final.mp4`, writes `metadata.json`.
  9. System prints a stage-timing summary table.
- **Postconditions**: `final.mp4` and `metadata.json` exist; `job.json`
  records every stage as `done` with its config hash.
- **Alternate flows**:
  - A1 (consent missing): flow ends at step 3 with a printed error and
    exit code 2; no job stages run.
  - A2 (script validation fails 3x): script stage raises
    `ScriptGenerationError`; job.json records `script` as `failed`;
    downstream stages don't run.
  - A3 (CUDA OOM during face stage): batch size is halved and retried down
    to a floor, then the stage falls back to CPU automatically.

## UC-2: Resume a partially-completed job

- **Actor**: Creator
- **Preconditions**: A job folder exists with a `job.json` recording at
  least one stage as `done`.
- **Main flow**:
  1. Creator runs `echoface resume <job-id>`.
  2. System loads the existing `Job` (topic, presenter, script_file, and
     every stage's recorded status/config hash) from `job.json`.
  3. For each stage in order, the system computes the current config hash
     and compares it + output-file existence against the recorded state.
  4. Matching stages are skipped ("up to date"); non-matching or
     not-yet-run stages execute.
- **Postconditions**: Every stage is `done`; unchanged stages were not
  re-executed (verified by stage timing showing "skipped").

## UC-3: Invalidate and re-render from a stage

- **Actor**: Creator
- **Main flow**:
  1. Creator runs `echoface clean <job-id> --from <stage>`.
  2. System resets `<stage>` and every downstream stage to `pending` in
     `job.json` and deletes their output files.
  3. Creator runs `echoface resume <job-id>` (or `make` with the same
     `--job-id`) to re-render from that point forward.
- **Postconditions**: Upstream stages' outputs and `done` status are
  untouched; the cleaned stages regenerate.

## UC-4: Check environment readiness

- **Actor**: Creator (typically on first setup, or after a config change)
- **Main flow**:
  1. Creator runs `echoface doctor`.
  2. System checks (each wrapped so one failure can't crash the report):
     ffmpeg/ffprobe, NVIDIA GPU, Ollama reachability + model presence,
     each venv, torch/CUDA in `envs\face`, configured model files,
     every presenter's consent, and (if `monetized: true`) licence
     compatibility of the selected models.
  3. System prints a table (OK/WARN/FAIL per check) and exits 0 unless a
     hard FAIL-level check occurred.
- **Postconditions**: Creator knows exactly what to fix before rendering.

## UC-5: Batch-render multiple topics unattended

- **Actor**: Creator
- **Main flow**:
  1. Creator writes one topic per line to a text file.
  2. Creator runs `echoface batch --file topics.txt [--presenter ...]`.
  3. System runs UC-1 once per line, auto-generating a job ID per topic.
  4. On any single job's failure, the system logs the error and continues
     to the next topic rather than aborting the batch.
- **Postconditions**: One `output/<job-id>/` per topic line, each either
  fully rendered or recorded with its failure in the console output.
