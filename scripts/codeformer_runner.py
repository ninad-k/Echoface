"""Real CodeFormer face restoration runner, executed inside envs\\face by
echoface.stages.face.FaceStage._apply_restore (via subprocess).

CodeFormer (sczhou/CodeFormer) is a second restoration option alongside
GFPGAN — generally regarded as producing more natural-looking (less
"plastic") restoration at the cost of a slightly heavier model. **Its
weights are S-Lab License 1.0, non-commercial** — see
models/licenses.yaml and models/MODELS.md.

This imports CodeFormer's own vendored `basicsr`/`facelib` packages
directly (vendor/CodeFormer ships its own copies of both, independent of
the pip-installed `basicsr` GFPGAN uses — see
vendor/patches/patch_codeformer.py for the one fix needed: a manually
written basicsr/version.py, since CodeFormer's repo doesn't ship one
pre-generated and its setup.py has the same PEP-667 issue documented for
the pip basicsr package in ADR-0003). The per-frame loop mirrors
vendor/CodeFormer/inference_codeformer.py's own logic closely enough to
produce the same output, with a region-blend step
(echoface.util.restore_blend) inserted before paste-back for
`--region mouth`.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

VENDOR_ROOT = Path(__file__).resolve().parent.parent / "vendor" / "CodeFormer"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Real CodeFormer restoration (echoface runner)")
    p.add_argument("--input", required=True, help="lip-synced video to restore")
    p.add_argument("--outfile", required=True)
    p.add_argument(
        "--model_path", default=None, help="defaults to vendor/CodeFormer/weights/CodeFormer/codeformer.pth"
    )
    p.add_argument("--device", choices=["cuda", "cpu"], default="cuda")
    p.add_argument(
        "--fidelity_weight",
        type=float,
        default=0.5,
        help="0=more identity-preserving, 1=more faithful to input",
    )
    p.add_argument("--only_center_face", action="store_true", default=True)
    p.add_argument("--region", choices=["face", "mouth"], default="face")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    input_path = str(Path(args.input).resolve())
    outfile = Path(args.outfile).resolve()
    model_path = (
        str(Path(args.model_path).resolve())
        if args.model_path
        else str(VENDOR_ROOT / "weights" / "CodeFormer" / "codeformer.pth")
    )

    import os

    os.chdir(VENDOR_ROOT)
    sys.path.insert(0, str(VENDOR_ROOT))

    import cv2
    import numpy as np
    import torch
    from basicsr.archs.codeformer_arch import CodeFormer
    from basicsr.utils import img2tensor, tensor2img
    from facelib.utils.face_restoration_helper import FaceRestoreHelper
    from torchvision.transforms.functional import normalize
    from tqdm import tqdm

    from echoface.util.restore_blend import blend_region

    device = args.device
    net = CodeFormer(
        dim_embd=512, codebook_size=1024, n_head=8, n_layers=9, connect_list=["32", "64", "128", "256"]
    ).to(device)
    checkpoint = torch.load(model_path, map_location=device, weights_only=False)
    net.load_state_dict(checkpoint["params_ema"])
    net.eval()

    face_helper = FaceRestoreHelper(
        upscale_factor=1,
        face_size=512,
        crop_ratio=(1, 1),
        det_model="retinaface_resnet50",
        save_ext="png",
        use_parse=True,
        device=device,
    )

    cap = cv2.VideoCapture(input_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    with tempfile.TemporaryDirectory(prefix="echoface_codeformer_") as tmpdir:
        silent_path = Path(tmpdir) / "restored_silent.avi"
        writer = cv2.VideoWriter(str(silent_path), cv2.VideoWriter_fourcc(*"XVID"), fps, (width, height))

        pbar = tqdm(
            total=n_frames if n_frames > 0 else None, desc=f"CodeFormer restore (region={args.region})"
        )
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            face_helper.clean_all()
            face_helper.read_image(frame)
            num_faces = face_helper.get_face_landmarks_5(
                only_center_face=args.only_center_face, resize=640, eye_dist_threshold=5
            )
            restored_img = frame
            if num_faces > 0:
                face_helper.align_warp_face()
                for cropped_face in face_helper.cropped_faces:
                    cropped_face_t = img2tensor(cropped_face / 255.0, bgr2rgb=True, float32=True)
                    normalize(cropped_face_t, (0.5, 0.5, 0.5), (0.5, 0.5, 0.5), inplace=True)
                    cropped_face_t = cropped_face_t.unsqueeze(0).to(device)
                    try:
                        with torch.no_grad():
                            output = net(cropped_face_t, w=args.fidelity_weight, adain=True)[0]
                            restored_face = tensor2img(output, rgb2bgr=True, min_max=(-1, 1))
                        del output
                        if device == "cuda":
                            torch.cuda.empty_cache()
                    except RuntimeError as error:
                        print(f"\tFailed inference for CodeFormer: {error}")
                        restored_face = tensor2img(cropped_face_t, rgb2bgr=True, min_max=(-1, 1))
                    restored_face = restored_face.astype("uint8")
                    blended = blend_region(np.asarray(cropped_face), restored_face, region=args.region)
                    face_helper.add_restored_face(blended, cropped_face)

                face_helper.get_inverse_affine(None)
                restored_img = face_helper.paste_faces_to_input_image(upsample_img=None)

            if restored_img.shape[:2] != (height, width):
                restored_img = cv2.resize(restored_img, (width, height))
            writer.write(restored_img)
            pbar.update(1)
        pbar.close()
        cap.release()
        writer.release()

        outfile.parent.mkdir(parents=True, exist_ok=True)
        mux_cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(silent_path),
            "-i",
            input_path,
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
            str(outfile),
        ]
        result = subprocess.run(mux_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(result.stdout, file=sys.stdout)
            print(result.stderr, file=sys.stderr)
            return result.returncode

    print(f"CodeFormer: wrote {outfile}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
