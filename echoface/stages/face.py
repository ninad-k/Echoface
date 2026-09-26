"""Face stage: presenter + voice_16k.wav -> face.mp4 (talking head).

Engines: wav2lip (default, subprocess into envs\\face), sadtalker (M8,
same venv, different script), dummy (ffmpeg-only loop, no GPU/model files —
used for smoke tests). Includes OOM-retry with batch-size halving then CPU
fallback, ping-pong idle-loop extension, long-audio chunking + concat, a
per-presenter face-detection box cache, and optional GFPGAN restoration.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from echoface.stages.base import Stage
from echoface.util import ffmpeg as ffm
from echoface.util.gpu import detect_gpu, unload_ollama_model
from echoface.util.proc import resolve_exe

OOM_MARKERS = (
    "cuda out of memory",
    "out of memory",
    "cudnn_status_alloc_failed",
    "cublas_status_alloc_failed",
)


class FaceEngineError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Face-detection box cache
# ---------------------------------------------------------------------------


class FaceBoxCache:
    """Caches face-detection boxes per presenter video, keyed by a hash of
    the video's path + size + mtime, so repeat renders skip re-detecting.
    """

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_path = cache_dir / "facecache.json"

    @staticmethod
    def key_for(video_path: Path) -> str:
        """Stable identity key for a presenter source file (the ORIGINAL
        idle/photo asset, not any ffmpeg-ping-ponged temp copy), used both
        for our own bookkeeping cache and passed to the real Wav2Lip runner
        subprocess so its per-frame face-box cache can key on it too."""
        stat = video_path.stat()
        raw = f"{video_path.resolve()}:{stat.st_size}:{int(stat.st_mtime)}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    # kept for backwards compatibility with any internal callers
    _key = key_for

    def _load(self) -> dict:
        if self.cache_path.exists():
            try:
                return json.loads(self.cache_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {}
        return {}

    def get(self, video_path: Path) -> dict | None:
        data = self._load()
        return data.get(self.key_for(video_path))

    def set(self, video_path: Path, boxes: dict) -> None:
        data = self._load()
        data[self.key_for(video_path)] = boxes
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# OOM-retry runner
# ---------------------------------------------------------------------------

RunFn = Callable[..., subprocess.CompletedProcess]


def _looks_like_oom(text: str) -> bool:
    lowered = (text or "").lower()
    return any(marker in lowered for marker in OOM_MARKERS)


def run_with_oom_retry(
    build_cmd: Callable[[int, str], list[str]],
    *,
    initial_batch_size: int,
    device: str,
    min_batch_size: int = 4,
    run_fn: RunFn = subprocess.run,
    logger=None,
) -> tuple[subprocess.CompletedProcess, int, str]:
    """Run a face-model subprocess, halving batch_size on CUDA OOM and
    falling back to CPU once batch_size can't be halved further.

    ``build_cmd(batch_size, device)`` must return the full argv list.
    Returns (completed_process, final_batch_size, final_device).
    Raises FaceEngineError if all attempts fail.
    """
    batch_size = initial_batch_size
    current_device = device
    last_error = ""

    while True:
        cmd = build_cmd(batch_size, current_device)
        if logger:
            logger.info(f"[face] running (batch_size={batch_size}, device={current_device})")
        result = run_fn(cmd, capture_output=True, text=True)
        combined = (result.stdout or "") + (result.stderr or "")
        if result.returncode == 0:
            return result, batch_size, current_device

        last_error = combined
        if not _looks_like_oom(combined):
            raise FaceEngineError(f"face engine failed (not OOM): {combined[-2000:]}")

        if current_device == "cuda" and batch_size > min_batch_size:
            batch_size = max(batch_size // 2, min_batch_size)
            if logger:
                logger.warning(f"[face] CUDA OOM, halving batch_size to {batch_size}")
            continue
        if current_device == "cuda":
            current_device = "cpu"
            batch_size = initial_batch_size
            if logger:
                logger.warning("[face] CUDA OOM persists at minimum batch size, falling back to CPU")
            continue
        raise FaceEngineError(f"face engine failed on CPU as well: {last_error[-2000:]}")


# ---------------------------------------------------------------------------
# Idle-loop / chunk helpers (ffmpeg based)
# ---------------------------------------------------------------------------


def build_looped_idle_video(idle_path: Path, target_duration_s: float, out_path: Path, fps: int = 25) -> None:
    """Ensure the idle clip covers target_duration_s by ping-ponging
    (forward, then reversed, repeating) and trimming to the exact length.
    If the clip already covers the duration, just trims/copies it.
    """
    info = ffm.probe(idle_path)
    plan = ffm.build_ping_pong_plan(info.duration_s, target_duration_s)
    if not plan:
        ffm.run_ffmpeg(
            ["-i", str(idle_path), "-t", f"{target_duration_s:.3f}", "-r", str(fps), str(out_path)]
        )
        return

    with tempfile.TemporaryDirectory(prefix="echoface_pingpong_") as tmpdir:
        tmp = Path(tmpdir)
        segment_files = []
        for i, (direction, _dur) in enumerate(plan):
            seg_out = tmp / f"seg_{i:03d}.mp4"
            if direction == "forward":
                ffm.run_ffmpeg(["-i", str(idle_path), "-r", str(fps), str(seg_out)])
            else:
                ffm.run_ffmpeg(["-i", str(idle_path), "-vf", "reverse", "-r", str(fps), str(seg_out)])
            segment_files.append(seg_out)

        concat_list = tmp / "concat.txt"
        concat_list.write_text("\n".join(f"file '{p.as_posix()}'" for p in segment_files), encoding="utf-8")
        looped = tmp / "looped.mp4"
        ffm.run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(looped)])
        ffm.run_ffmpeg(["-i", str(looped), "-t", f"{target_duration_s:.3f}", str(out_path)])


def concat_video_chunks(chunk_paths: list[Path], out_path: Path) -> None:
    if len(chunk_paths) == 1:
        shutil.copyfile(chunk_paths[0], out_path)
        return
    with tempfile.TemporaryDirectory(prefix="echoface_concat_") as tmpdir:
        concat_list = Path(tmpdir) / "concat.txt"
        concat_list.write_text(
            "\n".join(f"file '{p.resolve().as_posix()}'" for p in chunk_paths), encoding="utf-8"
        )
        ffm.run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(out_path)])


# ---------------------------------------------------------------------------
# Engines
# ---------------------------------------------------------------------------


class FaceEngine:
    def render(self, *, face_source: Path, audio_path: Path, out_path: Path, cfg, logger=None) -> None:
        raise NotImplementedError


class Wav2LipEngine(FaceEngine):
    """Real engine: shells into envs\\face and runs scripts/wav2lip_runner.py
    (our own driver — see that file's docstring for why it isn't a patched
    copy of vendor/Wav2Lip/inference.py)."""

    def __init__(
        self,
        python_exe: str = "envs/face/Scripts/python.exe",
        script_path: str = "scripts/wav2lip_runner.py",
        checkpoint: str = "models/wav2lip/wav2lip_gan.pth",
    ):
        self.python_exe = python_exe
        self.script_path = script_path
        self.checkpoint = checkpoint

    def render(self, *, face_source: Path, audio_path: Path, out_path: Path, cfg, logger=None) -> None:
        device = cfg.device
        if device == "auto":
            device = "cuda" if detect_gpu().available else "cpu"

        # Stable cache identity is the ORIGINAL presenter file, computed
        # before any ping-pong extension below (which writes a new temp
        # file each call and would otherwise defeat the cache).
        cache_dir = face_source.parent
        cache_key = FaceBoxCache.key_for(face_source)
        cache_file = cache_dir / "facecache.json"

        # Ping-pong extend a short idle clip to cover the audio, per
        # Section 8.3 — avoids the jarring hard-cut loop the vendor
        # inference.py does on its own (a plain modulo repeat).
        render_source = face_source
        temp_extended = None
        pingpong_original_frames = 0
        pingpong_fps = 25
        if face_source.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm"):
            audio_duration = ffm.probe(audio_path).duration_s
            clip_duration = ffm.probe(face_source).duration_s
            if clip_duration < audio_duration:
                temp_extended = out_path.parent / f"_{face_source.stem}_extended.mp4"
                build_looped_idle_video(face_source, audio_duration, temp_extended, fps=pingpong_fps)
                render_source = temp_extended
                # scripts/wav2lip_runner.py needs the ORIGINAL clip's frame
                # count (as re-encoded at pingpong_fps by
                # build_looped_idle_video) to dedupe face detection across
                # the forward/reverse halves via fold_pingpong_index.
                pingpong_original_frames = max(1, round(clip_duration * pingpong_fps))

        pads = " ".join(str(p) for p in cfg.pads)

        python_exe = resolve_exe(self.python_exe)

        def build_cmd(batch_size: int, dev: str) -> list[str]:
            cmd = [
                python_exe,
                self.script_path,
                "--checkpoint_path",
                self.checkpoint,
                "--face",
                str(render_source),
                "--audio",
                str(audio_path),
                "--outfile",
                str(out_path),
                "--pads",
                *pads.split(),
                "--face_det_batch_size",
                str(cfg.face_det_batch_size),
                "--wav2lip_batch_size",
                str(batch_size),
                "--resize_factor",
                str(cfg.resize_factor),
                "--device",
                dev,
                "--nosmooth",
                "--cache_file",
                str(cache_file),
                "--cache_key",
                cache_key,
                "--pingpong_original_frames",
                str(pingpong_original_frames),
            ]
            return cmd

        try:
            run_with_oom_retry(
                build_cmd,
                initial_batch_size=cfg.batch_size,
                device=device,
                logger=logger,
            )
        finally:
            if temp_extended and temp_extended.exists():
                temp_extended.unlink()


class SadTalkerEngine(FaceEngine):
    """M8: still-photo talking head, driven by our own scripts/sadtalker_runner.py
    (see that file's docstring for why it isn't vendor/SadTalker/inference.py
    invoked directly, and vendor/patches/sadtalker_numpy2_compat.patch for
    the 3 vendor fixes it needed). Uses the spec's 4 GB-safe settings by
    default: --still --preprocess crop --size 256, batch_size 1."""

    def __init__(
        self,
        python_exe: str = "envs/face/Scripts/python.exe",
        script_path: str = "scripts/sadtalker_runner.py",
        checkpoint_dir: str = "vendor/SadTalker/checkpoints",
    ):
        self.python_exe = python_exe
        self.script_path = script_path
        self.checkpoint_dir = checkpoint_dir

    def render(self, *, face_source: Path, audio_path: Path, out_path: Path, cfg, logger=None) -> None:
        device = cfg.device
        if device == "auto":
            device = "cuda" if detect_gpu().available else "cpu"

        python_exe = resolve_exe(self.python_exe)

        def build_cmd(batch_size: int, dev: str) -> list[str]:
            cmd = [
                python_exe,
                self.script_path,
                "--driven_audio",
                str(audio_path),
                "--source_image",
                str(face_source),
                "--outfile",
                str(out_path),
                "--checkpoint_dir",
                self.checkpoint_dir,
                "--still",
                "--preprocess",
                "crop",
                "--size",
                "256",
                "--batch_size",
                str(batch_size),
                "--device",
                dev,
            ]
            if cfg.restore == "gfpgan":
                # SadTalker's own AnimateFromCoeff applies GFPGAN inline
                # (more efficient than a separate decode/enhance/encode
                # pass) — FaceStage skips its own _apply_restore for this
                # engine so GFPGAN isn't applied twice.
                cmd += ["--enhancer", "gfpgan"]
            return cmd

        run_with_oom_retry(
            build_cmd,
            initial_batch_size=1,
            device=device,
            min_batch_size=1,
            logger=logger,
        )


class DummyFaceEngine(FaceEngine):
    """Loops the presenter's idle video (or a still image) to the audio's
    duration using pure ffmpeg — no GPU, no model weights. Used for M7
    end-to-end smoke tests."""

    def render(self, *, face_source: Path, audio_path: Path, out_path: Path, cfg, logger=None) -> None:
        audio_info = ffm.probe(audio_path)
        duration = max(audio_info.duration_s, 0.5)
        if face_source.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm"):
            build_looped_idle_video(face_source, duration, out_path)
        else:
            ffm.run_ffmpeg(
                [
                    "-loop",
                    "1",
                    "-i",
                    str(face_source),
                    "-t",
                    f"{duration:.3f}",
                    "-r",
                    "25",
                    "-vf",
                    "scale=720:-2",
                    "-pix_fmt",
                    "yuv420p",
                    str(out_path),
                ]
            )


def build_engine(cfg) -> FaceEngine:
    if cfg.engine == "wav2lip":
        return Wav2LipEngine()
    if cfg.engine == "sadtalker":
        return SadTalkerEngine()
    if cfg.engine == "dummy":
        return DummyFaceEngine()
    raise FaceEngineError(f"unknown face engine {cfg.engine!r}")


def resolve_face_source(presenter_dir: Path, source: str) -> Path:
    if source == "idle":
        candidate = presenter_dir / "idle.mp4"
        if candidate.exists():
            return candidate
        source = "photo"
    if source == "photo":
        for ext in (".png", ".jpg", ".jpeg"):
            candidate = presenter_dir / f"portrait{ext}"
            if candidate.exists():
                return candidate
    raise FaceEngineError(f"no idle.mp4 or portrait.* found for presenter dir {presenter_dir}")


class FaceStage(Stage):
    name = "face"

    def __init__(self, job, cfg, logger=None, presenter_dir: Path | None = None):
        super().__init__(job, cfg, logger)
        self.presenter_dir = presenter_dir or Path("assets/portraits") / cfg.presenter

    def inputs(self) -> list[Path]:
        return [self.job.path_for("voice_16k.wav")]

    def outputs(self) -> list[Path]:
        return [self.job.path_for("face.mp4")]

    def run(self) -> None:
        face_cfg = self.cfg.face
        audio_path = self.job.path_for("voice_16k.wav")
        out_path = self.job.path_for("face.mp4")
        face_source = resolve_face_source(self.presenter_dir, face_cfg.source)

        # Best-effort: free VRAM held by Ollama before claiming the GPU.
        if face_cfg.device in ("auto", "cuda") and face_cfg.engine != "dummy":
            unload_ollama_model(self.cfg.script.model, self.cfg.script.host)

        # Real face-detection box caching happens inside the Wav2Lip runner
        # subprocess (scripts/wav2lip_runner.py), keyed by
        # FaceBoxCache.key_for(face_source) — see Wav2LipEngine.render().
        engine = build_engine(face_cfg)

        audio_info = ffm.probe(audio_path)
        chunks = ffm.build_chunk_plan(audio_info.duration_s, face_cfg.chunk_seconds)

        if len(chunks) == 1:
            engine.render(
                face_source=face_source,
                audio_path=audio_path,
                out_path=out_path,
                cfg=face_cfg,
                logger=self.logger,
            )
        else:
            with tempfile.TemporaryDirectory(prefix="echoface_face_chunks_") as tmpdir:
                tmp = Path(tmpdir)
                chunk_outputs = []
                for i, (start, dur) in enumerate(chunks):
                    chunk_audio = tmp / f"chunk_{i:03d}.wav"
                    ffm.run_ffmpeg(
                        ["-i", str(audio_path), "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", str(chunk_audio)]
                    )
                    chunk_out = tmp / f"chunk_{i:03d}.mp4"
                    engine.render(
                        face_source=face_source,
                        audio_path=chunk_audio,
                        out_path=chunk_out,
                        cfg=face_cfg,
                        logger=self.logger,
                    )
                    chunk_outputs.append(chunk_out)
                concat_video_chunks(chunk_outputs, out_path)

        if face_cfg.restore == "gfpgan" and face_cfg.engine == "wav2lip":
            # SadTalker applies GFPGAN inline via its own --enhancer flag
            # (see SadTalkerEngine.render) — skip the separate pass here to
            # avoid restoring twice. Dummy engine also skips (no real face).
            self._apply_restore(out_path, "gfpgan")
        elif face_cfg.restore == "codeformer" and face_cfg.engine != "dummy":
            # CodeFormer has no engine that applies it inline, so it always
            # runs as this separate post-process pass regardless of
            # face.engine (wav2lip or sadtalker).
            self._apply_restore(out_path, "codeformer")

    def _apply_restore(self, video_path: Path, method: str) -> None:
        """Real GFPGAN or CodeFormer face/mouth restoration via
        scripts/{gfpgan,codeformer}_runner.py (subprocess into
        envs\\face). Restores in place (writes to a temp file, then
        replaces video_path). `face.restore_region` ("face" or "mouth")
        is passed through to either runner identically — see
        echoface.util.restore_blend."""
        restored = video_path.parent / f"_{video_path.stem}_restored.mp4"
        device = self.cfg.face.device
        if device == "auto":
            device = "cuda" if detect_gpu().available else "cpu"
        python_exe = resolve_exe("envs/face/Scripts/python.exe")
        region = self.cfg.face.restore_region
        # Resolve every relative path to absolute *before* handing an
        # explicit (non-repo-root) cwd to subprocess.run below — argv
        # entries are otherwise resolved against that cwd, not ours.
        video_path = video_path.resolve()
        restored = restored.resolve()

        if method == "gfpgan":
            cmd = [
                python_exe,
                resolve_exe("scripts/gfpgan_runner.py"),
                "--input",
                str(video_path),
                "--outfile",
                str(restored),
                "--model_path",
                resolve_exe("models/gfpgan/GFPGANv1.4.pth"),
                "--device",
                device,
                "--region",
                region,
            ]
        else:  # codeformer
            cmd = [
                python_exe,
                resolve_exe("scripts/codeformer_runner.py"),
                "--input",
                str(video_path),
                "--outfile",
                str(restored),
                "--device",
                device,
                "--region",
                region,
            ]

        if self.logger:
            self.logger.info(f"[face] running {method} restoration (region={region})...")
        # Explicit cwd (the job's own output dir, not the repo root) is
        # defence in depth against any third-party code (gfpgan/facexlib,
        # SadTalker's enhancer path) that still resolves *some* path
        # relative to cwd despite the fixes above — see
        # echoface/util/facexlib_pin.py and docs/qa/defect-log.md's
        # DEF-13. Any such stray directory then lands in a per-job
        # folder we already own and clean up, never the repo root.
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(video_path.parent))
        if result.returncode != 0:
            raise FaceEngineError(
                f"{method} restoration failed: {(result.stdout or '') + (result.stderr or '')}"
            )
        restored.replace(video_path)
