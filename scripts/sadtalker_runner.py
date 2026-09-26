"""Real SadTalker inference runner, executed inside envs\\face by
echoface.stages.face.SadTalkerEngine (via subprocess).

This is our own driver (not vendor/SadTalker/inference.py itself, and not
invoked as a subprocess against that file) that imports vendor/SadTalker's
pipeline stages directly — CropAndExtract (3DMM + crop), Audio2Coeff,
AnimateFromCoeff (face render, optional GFPGAN enhancer) — and drives them
with our own CLI contract: a single ``--outfile`` path (SadTalker's own
code instead writes a timestamped results directory and a same-named
".mp4"), and a failure mode (uncaught exception -> non-zero exit with a
CUDA-OOM-shaped message on OOM) that matches the orchestrator's
``run_with_oom_retry`` contract already used for Wav2Lip.

Needed exactly three small vendor patches to run at all under NumPy 2.x —
see vendor/patches/sadtalker_numpy2_compat.patch for the full account (all
three are `float(ndarray)`/ragged-array construction patterns that NumPy
1.x silently coerced and NumPy 2.x now raises on; none are Python-3.14
specific). No other code paths needed patching: kornia, scipy, skimage,
imageio and torch calls elsewhere in the pipeline ran clean on this
machine (torch 2.11+cu128, Python 3.14).

Much of the vendored code resolves asset/config paths relative to its own
repo root rather than accepting them as arguments (e.g. BFM fitting files
under src/config), so — matching how vendor/SadTalker/inference.py itself
is meant to be run — this runner chdir()s into vendor/SadTalker before
importing/running anything.

Usage (4 GB-safe settings from the spec: --still --preprocess crop --size
256, batch_size 1; use --enhancer gfpgan to run GFPGAN as part of the same
render):

    envs\\face\\Scripts\\python.exe scripts\\sadtalker_runner.py ^
        --driven_audio output\\<job>\\voice_16k.wav ^
        --source_image assets\\portraits\\<name>\\portrait.png ^
        --outfile output\\<job>\\face_raw.mp4 ^
        --checkpoint_dir vendor\\SadTalker\\checkpoints ^
        --still --preprocess crop --size 256 --batch_size 1 ^
        --device cuda [--enhancer gfpgan]
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path
from time import strftime

VENDOR_ROOT = Path(__file__).resolve().parent.parent / "vendor" / "SadTalker"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Real SadTalker inference (echoface runner)")
    p.add_argument("--driven_audio", required=True)
    p.add_argument("--source_image", required=True)
    p.add_argument("--outfile", required=True)
    p.add_argument("--checkpoint_dir", default=str(VENDOR_ROOT / "checkpoints"))
    p.add_argument("--pose_style", type=int, default=0)
    p.add_argument("--batch_size", type=int, default=1)
    p.add_argument("--size", type=int, default=256, choices=[256, 512])
    p.add_argument("--expression_scale", type=float, default=1.0)
    p.add_argument("--enhancer", default=None, help="e.g. 'gfpgan' (None = off)")
    p.add_argument("--background_enhancer", default=None)
    p.add_argument("--device", choices=["cuda", "cpu"], default="cuda")
    p.add_argument("--still", action="store_true", default=True)
    p.add_argument("--preprocess", default="crop", choices=["crop", "extcrop", "resize", "full", "extfull"])
    p.add_argument("--old_version", action="store_true", default=False)
    p.add_argument("--verbose", action="store_true", default=False)
    return p.parse_args()


def main() -> int:
    args = parse_args()

    # Resolve every user-supplied path to absolute BEFORE chdir'ing into
    # the vendor repo, since relative paths would otherwise resolve
    # against the wrong directory afterwards.
    driven_audio = str(Path(args.driven_audio).resolve())
    source_image = str(Path(args.source_image).resolve())
    outfile = Path(args.outfile).resolve()
    checkpoint_dir = str(Path(args.checkpoint_dir).resolve())

    os.chdir(VENDOR_ROOT)
    sys.path.insert(0, str(VENDOR_ROOT))

    from src.facerender.animate import AnimateFromCoeff  # type: ignore
    from src.generate_batch import get_data  # type: ignore
    from src.generate_facerender_batch import get_facerender_data  # type: ignore
    from src.test_audio2coeff import Audio2Coeff  # type: ignore
    from src.utils.init_path import init_path  # type: ignore
    from src.utils.preprocess import CropAndExtract  # type: ignore

    device = args.device
    config_dir = str(VENDOR_ROOT / "src" / "config")
    sadtalker_paths = init_path(checkpoint_dir, config_dir, args.size, args.old_version, args.preprocess)

    # Use a system temp dir (not a folder under the vendor checkout) so
    # repeat runs never leave stray results_* directories behind in
    # vendor/SadTalker, even if a later run crashes before cleanup.
    tmp_root = Path(tempfile.mkdtemp(prefix="echoface_sadtalker_"))
    save_dir = tmp_root / strftime("%Y_%m_%d_%H.%M.%S")
    save_dir.mkdir(parents=True, exist_ok=True)
    first_frame_dir = save_dir / "first_frame_dir"
    first_frame_dir.mkdir(parents=True, exist_ok=True)

    preprocess_model = CropAndExtract(sadtalker_paths, device)
    audio_to_coeff = Audio2Coeff(sadtalker_paths, device)
    animate_from_coeff = AnimateFromCoeff(sadtalker_paths, device)

    print("3DMM Extraction for source image")
    first_coeff_path, crop_pic_path, crop_info = preprocess_model.generate(
        source_image, str(first_frame_dir), args.preprocess, source_image_flag=True, pic_size=args.size
    )
    if first_coeff_path is None:
        raise RuntimeError(
            "SadTalker could not extract 3DMM coefficients (no face detected in source_image?)"
        )

    batch = get_data(first_coeff_path, driven_audio, device, ref_eyeblink_coeff_path=None, still=args.still)
    coeff_path = audio_to_coeff.generate(batch, str(save_dir), args.pose_style, ref_pose_coeff_path=None)

    data = get_facerender_data(
        coeff_path,
        crop_pic_path,
        first_coeff_path,
        driven_audio,
        args.batch_size,
        None,
        None,
        None,
        expression_scale=args.expression_scale,
        still_mode=args.still,
        preprocess=args.preprocess,
        size=args.size,
    )

    result = animate_from_coeff.generate(
        data,
        str(save_dir),
        source_image,
        crop_info,
        enhancer=args.enhancer,
        background_enhancer=args.background_enhancer,
        preprocess=args.preprocess,
        img_size=args.size,
    )

    outfile.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(result, str(outfile))
    if args.verbose:
        print(f"(intermediate files kept at {tmp_root})")
    else:
        shutil.rmtree(tmp_root, ignore_errors=True)

    print(f"SadTalker: wrote {outfile}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as exc:
        # Surface CUDA OOM in the shape echoface.stages.face.run_with_oom_retry
        # scans stdout/stderr for ("cuda out of memory" substring), same
        # contract as the Wav2Lip runner. torch's own OOM exception message
        # already contains this text; this except just guarantees a non-zero
        # exit with the message on stderr for our own raised RuntimeErrors too.
        print(f"SadTalker runner failed: {exc}", file=sys.stderr)
        sys.exit(1)
