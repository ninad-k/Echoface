"""Real GFPGAN face/mouth restoration runner, executed inside envs\\face by
echoface.stages.face.FaceStage._apply_restore (via subprocess).

Reads a lip-synced video (typically face_raw.mp4 from the Wav2Lip runner,
whose mouth region is characteristically blurry — see Section 8.3 / the
troubleshooting appendix), runs every frame through GFPGANv1.4 with
face-detect + paste-back, and re-muxes the result with the original audio
track.

This deliberately reuses TencentARC/GFPGAN's own GFPGANer machinery
(installed as a pip package into envs\\face, built from a patched
basicsr — see vendor/patches/patch_basicsr.py) rather than reimplementing
the architecture; only the driving/orchestration code here is ours. The
per-frame loop below is a close copy of `GFPGANer.enhance()`'s own
implementation (see that method's source for the original), NOT called
through `enhance()` directly, because `--region mouth` needs to blend at
the per-face, pre-paste-back stage (`echoface.util.restore_blend`) —
something `enhance()`'s all-in-one API doesn't expose a hook for.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
from tqdm import tqdm

from echoface.util.restore_blend import blend_region


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Real GFPGAN restoration (echoface runner)")
    p.add_argument("--input", required=True, help="lip-synced video to restore")
    p.add_argument("--outfile", required=True)
    p.add_argument("--model_path", default="models/gfpgan/GFPGANv1.4.pth")
    p.add_argument("--upscale", type=int, default=1, help="1 = keep original resolution")
    p.add_argument("--device", choices=["cuda", "cpu"], default="cuda")
    p.add_argument("--only_center_face", action="store_true", default=True)
    p.add_argument(
        "--region",
        choices=["face", "mouth"],
        default="face",
        help="'face' restores the whole detected face (default, matches pre-v0.2.0 behaviour); "
        "'mouth' blends the restoration back in only around the lower-center mouth region, "
        "feathered, leaving eyes/forehead untouched",
    )
    return p.parse_args()


def _restore_frame(restorer, img, only_center_face: bool, region: str):
    """Reimplementation of GFPGANer.enhance(..., paste_back=True)'s body,
    with a region-blend step inserted before add_restored_face. Returns
    the full pasted-back frame (or None if no face was detected)."""
    import numpy as np
    import torch
    from basicsr.utils import img2tensor, tensor2img
    from torchvision.transforms.functional import normalize

    face_helper = restorer.face_helper
    face_helper.clean_all()
    face_helper.read_image(img)
    face_helper.get_face_landmarks_5(only_center_face=only_center_face, eye_dist_threshold=5)
    face_helper.align_warp_face()

    if not face_helper.cropped_faces:
        return None

    for cropped_face in face_helper.cropped_faces:
        cropped_face_t = img2tensor(cropped_face / 255.0, bgr2rgb=True, float32=True)
        normalize(cropped_face_t, (0.5, 0.5, 0.5), (0.5, 0.5, 0.5), inplace=True)
        cropped_face_t = cropped_face_t.unsqueeze(0).to(restorer.device)
        try:
            with torch.no_grad():
                output = restorer.gfpgan(cropped_face_t, return_rgb=False, weight=0.5)[0]
                restored_face = tensor2img(output.squeeze(0), rgb2bgr=True, min_max=(-1, 1))
        except RuntimeError as error:
            print(f"\tFailed inference for GFPGAN: {error}.")
            restored_face = cropped_face
        restored_face = restored_face.astype("uint8")
        blended = blend_region(np.asarray(cropped_face), np.asarray(restored_face), region=region)
        face_helper.add_restored_face(blended)

    face_helper.get_inverse_affine(None)
    return face_helper.paste_faces_to_input_image(upsample_img=None)


def main() -> int:
    args = parse_args()
    from gfpgan import GFPGANer

    restorer = GFPGANer(
        model_path=args.model_path,
        upscale=args.upscale,
        arch="clean",
        channel_multiplier=2,
        bg_upsampler=None,
        device=args.device,
    )

    cap = cv2.VideoCapture(args.input)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    with tempfile.TemporaryDirectory(prefix="echoface_gfpgan_") as tmpdir:
        silent_path = Path(tmpdir) / "restored_silent.avi"
        writer = cv2.VideoWriter(str(silent_path), cv2.VideoWriter_fourcc(*"XVID"), fps, (width, height))

        pbar = tqdm(total=n_frames if n_frames > 0 else None, desc=f"GFPGAN restore (region={args.region})")
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            restored = _restore_frame(restorer, frame, args.only_center_face, args.region)
            if restored is not None:
                if restored.shape[:2] != (height, width):
                    restored = cv2.resize(restored, (width, height))
                writer.write(restored)
            else:
                writer.write(frame)
            pbar.update(1)
        pbar.close()
        cap.release()
        writer.release()

        Path(args.outfile).parent.mkdir(parents=True, exist_ok=True)
        mux_cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(silent_path),
            "-i",
            args.input,
            "-map",
            "0:v:0",
            "-map",
            "1:a:0?",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            args.outfile,
        ]
        result = subprocess.run(mux_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(result.stdout, file=sys.stdout)
            print(result.stderr, file=sys.stderr)
            return result.returncode

    print(f"GFPGAN: wrote {args.outfile}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
