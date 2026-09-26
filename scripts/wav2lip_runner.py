"""Real Wav2Lip inference runner, executed inside envs\\face by
echoface.stages.face.Wav2LipEngine (via subprocess, so the orchestrator
venv never needs torch/opencv/librosa).

This is a from-scratch driver (not a patched copy of vendor/Wav2Lip's
inference.py) that:
  - imports vendor/Wav2Lip's model architecture (models/wav2lip.py, pure
    torch) and its S3FD face detector (face_detection/, pure torch+cv2) and
    audio pipeline (audio.py, patched for modern librosa kwargs — see
    vendor/patches/wav2lip_audio_librosa_kwargs.patch) directly, rather than
    reimplementing mel-spectrogram extraction, so numerics exactly match
    what the checkpoint was trained on.
  - implements a REAL, persistent face-detection box cache (JSON, keyed by
    a caller-supplied stable key + frame count), so repeat renders of the
    same presenter/duration skip S3FD entirely.
  - raises a RuntimeError whose message contains "CUDA out of memory" on
    CUDA OOM (torch's own exception text already does this), which is the
    contract echoface.stages.face.run_with_oom_retry's orchestrator-side
    retry loop scans for — batch-size halving and CPU fallback live in the
    orchestrator, not here, so this script just needs to fail loudly and
    exit non-zero on OOM.

Usage (matches the command shape in Section 8.3 of the spec, plus a few
cache/runner-specific flags):

    envs\\face\\Scripts\\python.exe scripts\\wav2lip_runner.py ^
        --checkpoint_path models\\wav2lip\\wav2lip_gan.pth ^
        --face assets\\portraits\\anchor1\\idle.mp4 ^
        --audio output\\<job>\\voice_16k.wav ^
        --outfile output\\<job>\\face_raw.mp4 ^
        --pads 0 15 0 0 --face_det_batch_size 4 --wav2lip_batch_size 32 ^
        --resize_factor 1 --device cuda --nosmooth ^
        --cache_file assets\\portraits\\anchor1\\facecache.json ^
        --cache_key <sha256 of the ORIGINAL idle/photo file>
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
import torch

VENDOR_ROOT = Path(__file__).resolve().parent.parent / "vendor" / "Wav2Lip"

MEL_STEP_SIZE = 16


def _import_vendor():
    """Import vendor/Wav2Lip's audio.py, models, and face_detection with
    vendor root temporarily first on sys.path (its modules use bare
    imports like `import audio`, `from models import Wav2Lip`)."""
    sys.path.insert(0, str(VENDOR_ROOT))
    try:
        import audio  # type: ignore
        import face_detection  # type: ignore

        from models import Wav2Lip  # type: ignore
    finally:
        sys.path.remove(str(VENDOR_ROOT))
    return audio, Wav2Lip, face_detection


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Real Wav2Lip inference (echoface runner)")
    p.add_argument("--checkpoint_path", required=True)
    p.add_argument("--face", required=True)
    p.add_argument("--audio", required=True)
    p.add_argument("--outfile", required=True)
    p.add_argument("--pads", nargs=4, type=int, default=[0, 15, 0, 0])
    p.add_argument("--face_det_batch_size", type=int, default=4)
    p.add_argument("--wav2lip_batch_size", type=int, default=32)
    p.add_argument("--resize_factor", type=int, default=1)
    p.add_argument("--device", choices=["cuda", "cpu"], default="cuda")
    p.add_argument("--nosmooth", action="store_true")
    p.add_argument("--fps", type=float, default=25.0)
    p.add_argument("--cache_file", default=None, help="JSON face-box cache path")
    p.add_argument("--cache_key", default=None, help="stable key for the presenter/source clip")
    return p.parse_args()


def load_frames(face_path: Path, resize_factor: int) -> tuple[list, float]:
    if face_path.suffix.lower() in (".jpg", ".jpeg", ".png"):
        frame = cv2.imread(str(face_path))
        if frame is None:
            raise ValueError(f"could not read image {face_path}")
        return [frame], 25.0
    cap = cv2.VideoCapture(str(face_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frames = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if resize_factor > 1:
            frame = cv2.resize(frame, (frame.shape[1] // resize_factor, frame.shape[0] // resize_factor))
        frames.append(frame)
    cap.release()
    if not frames:
        raise ValueError(f"no frames read from {face_path}")
    return frames, fps


def get_smoothened_boxes(boxes: np.ndarray, t: int) -> np.ndarray:
    for i in range(len(boxes)):
        window = boxes[len(boxes) - t :] if i + t > len(boxes) else boxes[i : i + t]
        boxes[i] = np.mean(window, axis=0)
    return boxes


class BoxCache:
    """Real, persistent face-detection box cache. Keyed by a caller-supplied
    stable identity (the ORIGINAL presenter idle/photo file, not any
    ffmpeg-ping-ponged temp copy) plus the frame count being processed, so
    a repeat render of the same presenter at the same target duration skips
    S3FD detection entirely."""

    def __init__(self, path: Path | None):
        self.path = path
        self._data = {}
        if path and path.exists():
            try:
                self._data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self._data = {}

    def _cache_id(self, key: str, n_frames: int) -> str:
        return f"{key}:{n_frames}"

    def get(self, key: str | None, n_frames: int):
        if not key:
            return None
        return self._data.get(self._cache_id(key, n_frames))

    def set(self, key: str | None, n_frames: int, boxes: list) -> None:
        if not key or not self.path:
            return
        self._data[self._cache_id(key, n_frames)] = boxes
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data), encoding="utf-8")


def face_detect(
    images, face_detection_module, device, batch_size, pads, nosmooth, cache: BoxCache, cache_key
):
    n_frames = len(images)
    cached = cache.get(cache_key, n_frames)
    if cached is not None:
        boxes = np.array(cached, dtype=float)
    else:
        detector = face_detection_module.FaceAlignment(
            face_detection_module.LandmarksType._2D, flip_input=False, device=device
        )
        predictions = []
        bs = batch_size
        i = 0
        while i < len(images):
            batch = np.array(images[i : i + bs])
            predictions.extend(detector.get_detections_for_batch(batch))
            i += bs
        del detector

        raw_boxes = []
        pady1, pady2, padx1, padx2 = pads
        for rect, image in zip(predictions, images, strict=True):
            if rect is None:
                raise ValueError(
                    "Face not detected in one or more frames of the presenter clip. "
                    "Use a front-facing, well-lit portrait/idle clip."
                )
            y1 = max(0, rect[1] - pady1)
            y2 = min(image.shape[0], rect[3] + pady2)
            x1 = max(0, rect[0] - padx1)
            x2 = min(image.shape[1], rect[2] + padx2)
            raw_boxes.append([x1, y1, x2, y2])
        boxes = np.array(raw_boxes, dtype=float)
        cache.set(cache_key, n_frames, boxes.tolist())

    if not nosmooth:
        boxes = get_smoothened_boxes(boxes, t=5)
    boxes = boxes.astype(int)
    return [
        (image[y1:y2, x1:x2], (y1, y2, x1, x2)) for image, (x1, y1, x2, y2) in zip(images, boxes, strict=True)
    ]


def datagen(frames, mels, face_det_results, img_size, batch_size):
    img_batch, mel_batch, frame_batch, coords_batch = [], [], [], []
    for i, m in enumerate(mels):
        idx = i % len(frames)
        frame_to_save = frames[idx].copy()
        face, coords = face_det_results[idx]
        face = cv2.resize(face, (img_size, img_size))

        img_batch.append(face)
        mel_batch.append(m)
        frame_batch.append(frame_to_save)
        coords_batch.append(coords)

        if len(img_batch) >= batch_size:
            yield _finalize_batch(img_batch, mel_batch, frame_batch, coords_batch, img_size)
            img_batch, mel_batch, frame_batch, coords_batch = [], [], [], []

    if img_batch:
        yield _finalize_batch(img_batch, mel_batch, frame_batch, coords_batch, img_size)


def _finalize_batch(img_batch, mel_batch, frame_batch, coords_batch, img_size):
    img_batch_np = np.asarray(img_batch)
    mel_batch_np = np.asarray(mel_batch)
    img_masked = img_batch_np.copy()
    img_masked[:, img_size // 2 :] = 0
    img_batch_np = np.concatenate((img_masked, img_batch_np), axis=3) / 255.0
    mel_batch_np = np.reshape(
        mel_batch_np, [len(mel_batch_np), mel_batch_np.shape[1], mel_batch_np.shape[2], 1]
    )
    return img_batch_np, mel_batch_np, frame_batch, coords_batch


def load_wav2lip_model(checkpoint_path: str, device: str, Wav2LipCls):
    """Load the checkpoint. The official wav2lip_gan.pth distributed via
    the README's Google Drive link is a TorchScript archive (not a plain
    state_dict), so try torch.jit.load first and fall back to the
    state_dict format used by some other Wav2Lip checkpoint mirrors."""
    try:
        model = torch.jit.load(checkpoint_path, map_location=device)
        model.eval()
        return model
    except RuntimeError:
        pass
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    state_dict = checkpoint.get("state_dict", checkpoint)
    new_state_dict = {k.replace("module.", ""): v for k, v in state_dict.items()}
    model = Wav2LipCls()
    model.load_state_dict(new_state_dict)
    model = model.to(device)
    return model.eval()


def main() -> int:
    args = parse_args()
    audio, Wav2LipCls, face_detection_module = _import_vendor()

    device = args.device
    face_path = Path(args.face)
    frames, fps = load_frames(face_path, args.resize_factor)
    is_static = face_path.suffix.lower() in (".jpg", ".jpeg", ".png")
    if is_static:
        fps = args.fps

    wav = audio.load_wav(args.audio, 16000)
    mel = audio.melspectrogram(wav)
    if np.isnan(mel.reshape(-1)).sum() > 0:
        raise ValueError("Mel spectrogram contains NaN (check the input audio).")

    mel_chunks = []
    mel_idx_multiplier = 80.0 / fps
    i = 0
    while True:
        start_idx = int(i * mel_idx_multiplier)
        if start_idx + MEL_STEP_SIZE > len(mel[0]):
            mel_chunks.append(mel[:, len(mel[0]) - MEL_STEP_SIZE :])
            break
        mel_chunks.append(mel[:, start_idx : start_idx + MEL_STEP_SIZE])
        i += 1

    detect_frames = [frames[0]] if is_static else frames
    cache = BoxCache(Path(args.cache_file) if args.cache_file else None)
    face_det_results = face_detect(
        detect_frames,
        face_detection_module,
        device,
        args.face_det_batch_size,
        args.pads,
        args.nosmooth,
        cache,
        args.cache_key,
    )
    if is_static:
        face_det_results = face_det_results * 1  # single-entry list; datagen cycles via % len(frames)
        frames = [frames[0]]

    model = load_wav2lip_model(args.checkpoint_path, device, Wav2LipCls)

    img_size = 96
    with tempfile.TemporaryDirectory(prefix="echoface_wav2lip_") as tmpdir:
        silent_path = Path(tmpdir) / "silent.avi"
        writer = None
        frame_h, frame_w = frames[0].shape[:2]
        writer = cv2.VideoWriter(str(silent_path), cv2.VideoWriter_fourcc(*"XVID"), fps, (frame_w, frame_h))

        for img_batch, mel_batch, frame_batch, coords_batch in datagen(
            frames, mel_chunks, face_det_results, img_size, args.wav2lip_batch_size
        ):
            img_t = torch.FloatTensor(np.transpose(img_batch, (0, 3, 1, 2))).to(device)
            mel_t = torch.FloatTensor(np.transpose(mel_batch, (0, 3, 1, 2))).to(device)
            with torch.no_grad():
                pred = model(mel_t, img_t)
            pred = pred.cpu().numpy().transpose(0, 2, 3, 1) * 255.0

            for p, f, c in zip(pred, frame_batch, coords_batch, strict=True):
                y1, y2, x1, x2 = c
                p = cv2.resize(p.astype(np.uint8), (x2 - x1, y2 - y1))
                f = f.copy()
                f[y1:y2, x1:x2] = p
                writer.write(f)
        writer.release()

        Path(args.outfile).parent.mkdir(parents=True, exist_ok=True)
        mux_cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(silent_path),
            "-i",
            args.audio,
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

    print(f"Wav2Lip: wrote {args.outfile} ({len(frames)} presenter frames, {len(mel_chunks)} mel chunks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
