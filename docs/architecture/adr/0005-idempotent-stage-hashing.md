# ADR-0005: Idempotent stages via per-stage config hashing

## Status
Accepted.

## Context
Renders are slow (face stage: 1.5–4+ minutes on the reference GPU) and a
job may need to be re-run after an interruption, a tweak to one stage's
config, or a deliberate `clean` of a later stage. Redoing every stage on
every invocation would make iteration painfully slow; blindly trusting
"the output file exists" would miss a config change that should invalidate
a cached result.

## Decision
Each stage's config-relevant subset (`EchofaceConfig.stage_config(name)`)
plus a few always-relevant global fields (presenter, language,
target_seconds) plus stage-specific extras (e.g. the topic string, for the
script stage) are hashed (`echoface/config.py::stage_hash`, sha256 of a
sorted-key JSON dump, truncated to 16 hex chars). `Job.is_stage_done`
skips a stage only if its recorded status is `done`, the recorded hash
equals the current hash, **and** every declared output file still exists.
Any one of those being false forces a real re-run.

## Consequences
- **Positive**: changing `face.restore` from `none` to `gfpgan` and
  re-running automatically redoes only the face stage (its hash changed)
  and downstream stages, while script/voice stay cached. Deleting an
  output file manually also correctly forces a re-run even if the hash
  matches.
- **Negative**: the hash is a coarse, all-or-nothing signal per stage —
  changing an *unrelated* field within the same stage's config section
  still invalidates that whole stage's cache (e.g. changing
  `voice.speed` invalidates voice even though `voice.pause_ms` is
  unaffected in principle). Accepted: finer-grained caching would add
  real complexity for a marginal win, since voice/face renders aren't
  typically iterated field-by-field.
- A real bug was found and fixed in this mechanism during development:
  `Job.create()` originally always wrote a *blank* `job.json` when given
  an explicit `--job-id`, discarding all prior stage state even when
  nothing had changed — see `docs/qa/defect-log.md` DEF-3. Fixed to load
  the existing job if one exists at that path.
