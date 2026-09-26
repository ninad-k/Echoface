# Licence Matrix

Two layers: the **code** Echoface depends on/vendors, and the **model
weights** it downloads. Model weight licences are frequently more
restrictive than the code that runs them — check both before monetising.

## Echoface itself
MIT (`LICENSE`).

## Vendored / cloned code (`vendor/`, not committed — cloned by setup)

| Repo | Licence | Commercial use of the code? |
|---|---|---|
| Rudrabha/Wav2Lip | No explicit repo licence file found upstream at time of writing — treat as "all rights reserved by default" for anything beyond fair-use research/reference until the upstream project states otherwise | Not confirmed — see model-weight row below regardless, since the weights are explicitly research/non-commercial |
| OpenTalker/SadTalker | Apache-2.0 (code), except listed third-party components | Yes, for the code; verify each checkpoint's own terms (below) |
| TencentARC/GFPGAN | Apache-2.0 | Yes, for the code |

## Model weights (see `models/MODELS.md` for exact source URLs/SHA256)

| Model | Source | Licence | Commercial use? |
|---|---|---|---|
| qwen2.5:7b (Ollama) | ollama.com/library/qwen2.5 | Apache-2.0 / Qwen licence | Yes |
| Piper `en_US-lessac-medium` | rhasspy/piper-voices (HF) | MIT | Yes |
| Wav2Lip `wav2lip_gan.pth` | Wav2Lip README → Google Drive | **Research / non-commercial only** | **No** |
| S3FD face detector (`s3fd.pth`) | linked from Wav2Lip README | Research use (1adrianb/face-alignment) | Check before monetising |
| GFPGANv1.4.pth | TencentARC/GFPGAN GitHub release | Apache-2.0 (code); check the weights' own licence file for the model itself | Check |
| facexlib detection/parsing weights | xinntao/facexlib GitHub releases | Apache-2.0 | Yes |
| SadTalker checkpoints (M8) | OpenTalker/SadTalker GitHub releases | Apache-2.0 (code); underlying 3DMM/BFM/face-vid2vid sub-models each carry their own terms | Check each sub-model before monetising |
| faster-whisper `small` | Systran/faster-whisper-small (HF) | MIT (code); Whisper weights MIT | Yes |
| XTTS v2 (M8) | coqui/XTTS-v2 (HF) | **Coqui Public Model License (CPML) — non-commercial** | **No** |

## `echoface doctor`'s enforcement
`_check_monetization_licence` in `echoface/doctor.py` warns (not a hard
failure — the tool doesn't try to be a legal gate) when `monetized: true`
and `face.engine: wav2lip` (the currently-flagged non-commercial default)
is selected. It does not yet check every row above programmatically —
XTTS's CPML licence, for instance, is documented but not (yet)
cross-checked by `doctor`. See
`docs/project/improvements-and-known-issues.md`.

## Guidance if you intend to monetise
1. Run `echoface doctor` with `monetized: true` in config and read every
   warning.
2. Cross-reference every model you've selected against this table and
   `models/MODELS.md`.
3. For Wav2Lip specifically: either obtain commercial terms, switch
   `face.engine: sadtalker` (Apache-2.0 code — but still verify its
   sub-model checkpoints), or wait for a permissively-licensed lip-sync
   model to become available and add it as a new engine
   (`docs/dev/adding-a-stage-or-engine.md`).
4. For XTTS v2: do not use in monetised content under the CPML terms as
   downloaded; Piper (MIT) has no such restriction.
