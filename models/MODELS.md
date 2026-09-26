# Models

Every entry below was actually downloaded and verified on this machine
(RTX 5070 Laptop GPU, Python 3.14, torch 2.11+cu128) during provisioning.
`echoface doctor` warns about non-commercial models when `monetized: true`
by reading **[`models/licenses.yaml`](licenses.yaml)** (machine-readable,
kept consistent with the table below — see `echoface/licenses.py`), not
this file directly; this file is the human-readable version with exact
source URLs, versions, and SHA256 checksums.

| stage    | file                                            | source (official)                                                                 | version/date        | SHA256                                                            | licence                          | commercial |
|----------|--------------------------------------------------|-------------------------------------------------------------------------------------|----------------------|--------------------------------------------------------------------|-----------------------------------|------------|
| script   | qwen2.5:7b (Ollama)                              | https://ollama.com/library/qwen2.5                                                  | 7b, pulled 2026-09-26 | (Ollama-managed blob; `ollama show qwen2.5:7b` for its digest)     | Apache-2.0 / Qwen licence          | yes        |
| voice    | en_US-lessac-medium.onnx (+ .onnx.json)          | https://huggingface.co/rhasspy/piper-voices (official rhasspy org)                  | medium, 2026-09-26    | `5efe09e69902187827af646e1a6e9d269dee769f9877d17b16b1b46eeaaf019f` | MIT (Piper)                        | yes        |
| face     | wav2lip_gan.pth                                  | Rudrabha/Wav2Lip README -> Google Drive (official link in repo)                     | downloaded 2026-09-26  | `180cfd49d31d47f195d5bfc62830ffe2c40724b7bbbce6faadc73ac6ab1a3b8e` | **research / non-commercial only** | **no**     |
| face-det | s3fd.pth (S3FD face detector, used by Wav2Lip)   | https://www.adrianbulat.com/downloads/python-fan/s3fd-619a316812.pth (linked from Wav2Lip README) | -            | `619a31681264d3f7f7fc7a16a42cbbe8b23f31a256f75a366e5a1bcd59b33543` | research use (1adrianb/face-alignment) | check |
| restore  | GFPGANv1.4.pth                                   | https://github.com/TencentARC/GFPGAN/releases/download/v1.3.4/GFPGANv1.4.pth        | v1.4                 | `e2cd4703ab14f4d01fd1383a8a8b266f9a5833dacee8e6a79d3bf21a1b6be5ad`  | Apache-2.0 (code); weights for research/non-commercial use per GFPGAN's licence file | check |
| restore  | detection_Resnet50_Final.pth (facexlib, via GFPGAN) | https://github.com/xinntao/facexlib/releases/download/v0.1.0/detection_Resnet50_Final.pth | v0.1.0        | `6d1de9c2944f2ccddca5f5e010ea5ae64a39845a86311af6fdf30841b0a5a16d`  | Apache-2.0                         | yes        |
| restore  | parsing_parsenet.pth (facexlib, via GFPGAN)      | https://github.com/xinntao/facexlib/releases/download/v0.2.2/parsing_parsenet.pth    | v0.2.2                | `3d558d8d0e42c20224f13cf5a29c79eba2d59913419f945545d8cf7b72920de2`  | Apache-2.0                         | yes        |
| face(M8) | SadTalker_V0.0.2_256.safetensors                 | https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc                 | v0.0.2-rc             | `c211f5d6de003516bf1bbda9f47049a4c9c99133b1ab565c6961e5af16477bff`  | Apache-2.0 (code); check individual sub-model licences (3DMM/BFM, face-vid2vid) | check |
| face(M8) | SadTalker_V0.0.2_512.safetensors                 | https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc                 | v0.0.2-rc             | `0e063f7ff5258240bdb0f7690783a7b1374e6a4a81ce8fa33456f4cd49694340`  | as above                           | check      |
| face(M8) | mapping_00109-model.pth.tar                      | https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc                 | v0.0.2-rc             | `84a8642468a3fcfdd9ab6be955267043116c2bec2284686a5262f1eaf017f64c`  | as above                           | check      |
| face(M8) | mapping_00229-model.pth.tar                      | https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc                 | v0.0.2-rc             | `62a1e06006cc963220f6477438518ed86e9788226c62ae382ddc42fbcefb83f1`  | as above                           | check      |
| captions | faster-whisper "small" (Systran/faster-whisper-small) | https://huggingface.co/Systran/faster-whisper-small (official Systran org)      | small                | (HF-cached, auto-verified by huggingface_hub)                      | MIT (code); Whisper weights MIT    | yes        |
| voice(M8)| XTTS v2 (coqui-tts package, `tts_models/multilingual/multi-dataset/xtts_v2`) | https://huggingface.co/coqui/XTTS-v2 (official Coqui org)     | v2                    | not downloaded on this machine (import/env verified only — see README) | **Coqui Public Model License (CPML) — NON-COMMERCIAL** | **no** |
| restore (v0.2.0) | codeformer.pth | https://github.com/sczhou/CodeFormer/releases/download/v0.1.0/codeformer.pth (official GitHub release) | v0.1.0 | `1009e537e0c2a07d4cabce6355f53cb66767cd4b4297ec7a4a64ca4b8a5684b7` | **S-Lab License 1.0 — NON-COMMERCIAL** | **no** |

## Notes from this machine's provisioning run

- **Wav2Lip's `wav2lip_gan.pth`** turned out to be a TorchScript archive
  (`torch.jit.load` succeeds; a plain `torch.load` does not, since it's not
  a bare state_dict) — `scripts/wav2lip_runner.py` tries `torch.jit.load`
  first and falls back to the state_dict format for other mirrors/versions.
- Nothing under `models/` other than this file, or `vendor/*/checkpoints`,
  is committed to git (see `.gitignore`) — each machine downloads its own
  copies per `scripts/setup_windows.ps1` and the URLs above.
- **Monetisation**: `wav2lip_gan.pth` is research/non-commercial licensed.
  `echoface doctor` warns if `monetized: true` while `face.engine: wav2lip`
  is selected — see `echoface/doctor.py::_check_monetization_licence`. If
  you intend to monetise, either get commercial terms for Wav2Lip, switch
  to a permissively-licensed alternative, or use SadTalker (Apache-2.0
  code — but verify its 3DMM/BFM sub-model licences before monetising).
- **XTTS v2 weights were not downloaded** on this machine (only the
  `coqui-tts` package/import path was verified — see README's XTTS section
  for exactly what was and wasn't exercised). If you download them,
  `tts_models--multilingual--multi-dataset--xtts_v2` lands in the
  `envs\tts` Python's HF cache; record its resolved commit hash here.
