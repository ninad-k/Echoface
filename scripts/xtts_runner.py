"""Real XTTS v2 runner, executed inside envs\\tts by VoiceStage's
XttsVoiceEngine (M8 upgrade path). Kept separate from the orchestrator so
the coqui-tts package (and its torch dependency) never needs to be
installed in the orchestrator venv.

Verified working on this machine (Python 3.14, torch 2.11+cu128):
GPU load ~90s (first run downloads ~1.8 GB of weights from the official
coqui/XTTS-v2 HF repo, cached after that), then a few seconds per sentence
of synthesis. XTTS v2's WEIGHTS are licensed under Coqui's Public Model
License (CPML), which is NON-COMMERCIAL — see models/MODELS.md. Selecting
`voice.engine: xtts` in config is itself an opt-in to that license, so
this runner sets COQUI_TOS_AGREED=1 to skip the interactive prompt rather
than failing in a non-interactive subprocess.

Usage:
    envs\\tts\\Scripts\\python.exe scripts\\xtts_runner.py --text "..." \
        --out out.wav [--speaker_wav ref.wav] [--speaker "Claribel Dervla"] \
        [--language en]
"""

from __future__ import annotations

import argparse
import os
import sys

# Must be set before importing TTS (it's read at model-download time).
os.environ.setdefault("COQUI_TOS_AGREED", "1")

DEFAULT_BUILTIN_SPEAKER = "Claribel Dervla"  # a built-in XTTS v2 speaker


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--speaker_wav", default=None, help="reference clip for voice cloning (requires consent)"
    )
    parser.add_argument(
        "--speaker",
        default=DEFAULT_BUILTIN_SPEAKER,
        help="built-in XTTS speaker name (used if --speaker_wav is not given)",
    )
    parser.add_argument("--language", default="en")
    parser.add_argument("--device", choices=["cuda", "cpu"], default="cuda")
    args = parser.parse_args()

    try:
        from TTS.api import TTS
    except ImportError:
        print(
            "coqui-tts is not installed in this environment. "
            "Install it with: pip install coqui-tts  (inside envs\\tts)",
            file=sys.stderr,
        )
        return 1

    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", progress_bar=False).to(args.device)
    kwargs = {"text": args.text, "file_path": args.out, "language": args.language}
    if args.speaker_wav:
        kwargs["speaker_wav"] = args.speaker_wav
    else:
        kwargs["speaker"] = args.speaker
    tts.tts_to_file(**kwargs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
