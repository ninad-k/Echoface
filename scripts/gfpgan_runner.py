"""Real GFPGAN face/mouth restoration runner, executed inside envs\\face by
echoface.stages.face.FaceStage._apply_restore (via subprocess).

Reads a lip-synced video (typically face_raw.mp4 from the Wav2Lip runner,
whose mouth region is characteristically blurry — see Section 8.3 / the
troubleshooting appendix), runs every frame through GFPGANv1.4 with
face-detect + paste-back (so only the detected face region is sharpened,
the rest of the frame is untouched), and re-muxes the result with the
original audio track.

This deliberately reuses TencentARC/GFPGAN's own GFPGANer class (installed
as a pip package into envs\\face, built from a patched basicsr — see
vendor/patches/basicsr_setup_version_and_functional_tensor.py) rather than
reimplementing the architecture; only the driving/orchestration code here
is ours.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
from tqdm import tqdm


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Real GFPGAN restoration (echoface runner)")
    p.add_argument("--input", required=True, help="lip-synced video to restore")
    p.add_argument("--outfile", required=True)
    p.add_argument("--model_path", default="models/gfpgan/GFPGANv1.4.pth")
    p.add_argument("--upscale", type=int, default=1, help="1 = keep original resolution")
    p.add_argument("--device", choices=["cuda", "cpu"], default="cuda")
    p.add_argument("--only_center_face", action="store_true", default=True)
    return p.parse_args()


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

        pbar = tqdm(total=n_frames if n_frames > 0 else None, desc="GFPGAN restore")
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            _, _, restored = restorer.enhance(
                frame, has_aligned=False, only_center_face=args.only_center_face, paste_back=True
            )
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
