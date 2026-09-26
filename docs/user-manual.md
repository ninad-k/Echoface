# User Manual

Written for non-engineers who want to produce a talking-head Short.
For technical/setup detail, see `docs/ops/installation-deployment.md`.

## What Echoface does
You give it a topic (or your own script). It writes a short spoken script
with a local AI, turns that into speech, makes your chosen presenter's
photo or clip appear to say it, adds captions and background music, and
gives you back a finished vertical video ready to upload — all running on
your own computer, nothing sent to any company.

## 1. First-time setup
Follow `docs/ops/installation-deployment.md` (or the README's "Windows
setup" section) once. It involves installing Python, ffmpeg, Ollama, and
running one setup script. Budget an hour or two the first time, mostly
waiting for downloads.

## 2. Check everything's ready
```
echoface doctor
```
Green rows are good. Yellow ("WARN") rows tell you what's missing before
you try to render — read the "Detail" column.

## 3. Set up your presenter (and consent)
A "presenter" is a folder under `assets\portraits\<name>\` containing
either a short video of the person sitting still and blinking
(`idle.mp4`) or a single still photo (`portrait.png`/`.jpg`), plus a
`meta.yaml` file. **You must have written consent from the real person**
before using their likeness — see
`docs/security/responsible-use-consent-policy.md`. Echoface will refuse
to render without it; this isn't a suggestion, it's enforced.

For best results (per the original design spec): a front-facing, evenly
lit photo, at least 1024px, neutral closed mouth, no hair or hands
covering the mouth. A short clip of the person blinking naturally (rather
than a frozen photo) looks more alive.

## 4. Make your first video
```
echoface make --topic "3 habits of disciplined traders" --presenter <name>
```
This can take a few minutes (mostly the face-animation step). When done,
your video is at `output\<job-id>\final.mp4`, with a matching
`metadata.json` containing a title, description, and tags you can copy
into your upload form.

## 5. Using your own script instead
```
echoface make --script-file my_script.txt --presenter <name>
```
Write your script as plain text, one line per sentence — a hook line
first, then your points, then a closing line.

## 6. Batch-rendering several topics
Put one topic per line in a text file, then:
```
echoface batch --file topics.txt --presenter <name>
```
Good for queuing up a week's worth overnight.

## 7. Fixing a mistake without starting over
Didn't like the ending? Re-render just the captions and final assembly,
keeping the voice and face render:
```
echoface clean <job-id> --from captions
echoface resume <job-id>
```
Stage names, in order: `script`, `voice`, `face`, `captions`, `compose`.
`clean --from <stage>` invalidates that stage and everything after it.

## 8. Resuming an interrupted render
```
echoface resume <job-id>
```
Already-finished stages are skipped automatically.

## 9. Key config options
Edit `config\echoface.yaml` (or make a copy and pass `--config
your-config.yaml`). The ones you're most likely to touch:

- `compose.layout`: `face_top` (default), `full_face`, or `face_bottom`
  — where the face sits on screen.
- `face.engine`: `wav2lip` (default, subtle mouth-only movement) or
  `sadtalker` (photo only, more natural head motion, slower).
- `face.restore`: `gfpgan` (sharper face, default) or `none` (faster).
- `voice.speed`: >1.0 speaks faster, <1.0 slower.
- `compose.music`: path to a background music file (bring your own —
  royalty-free tracks only, not committed by this project).
- `monetized`: set `true` if the channel is monetised — makes `doctor`
  warn about models with non-commercial licences.

See `docs/ops/configuration-reference.md` for every option.

## 10. Quality tips (from the spec's own checklist)
- Hook in the first 2 seconds — no greetings or channel intros.
- One idea per Short, 25–45 seconds, short sentences.
- Cut or zoom every few seconds if you're editing further — Echoface's
  raw output is a static-camera talking head; light editing helps
  realism.
- Keep the same presenter and voice across your videos to build
  recognition.
- Tick your platform's synthetic-content disclosure toggle at upload —
  Echoface writes the disclosure text into `metadata.json`, but you still
  need to tick the platform's own setting (see
  `docs/security/ai-disclosure-policy.md`).

## FAQ

**Q: Does this need an internet connection?**
A: Only for the one-time setup (downloading Python packages and model
weights) and the script-writing step, which talks to Ollama *running on
your own machine*, not the internet. Everything else is fully offline.

**Q: Why did it refuse to render my presenter?**
A: You're missing a consent file, or `meta.yaml`'s `consent_ref` points
at a file that doesn't exist. See step 3 above.

**Q: The face looks static/robotic.**
A: That's an inherent limitation of local lip-sync models on modest
hardware (see the README's "Honest expectations"). Try `face.engine:
sadtalker` for more head motion, or a sharper/better-lit source photo.

**Q: Can I use this for a monetised YouTube channel?**
A: Check `docs/security/license-matrix.md` first — the default Wav2Lip
model is research/non-commercial licensed. Run `echoface doctor` with
`monetized: true` in your config to get a warning if your current setup
has a licence conflict.

**Q: It's using the wrong Ollama model / can't reach Ollama.**
A: Run `ollama serve` in a terminal, `ollama pull qwen2.5:7b` (or your
chosen model), and re-run `echoface doctor` to confirm.

**Q: Where do my finished videos go?**
A: `output\<job-id>\final.mp4`, alongside `metadata.json` (title,
description, tags) and every intermediate file for that render.
