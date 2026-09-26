"""Real-engine regression tests — actual GPU inference (Wav2Lip, GFPGAN,
CodeFormer) and a real Ollama call, on tiny inputs for speed. NOT run by
default (`pyproject.toml`'s `addopts` excludes `gpu`/`ollama` markers) —
these need `envs\\face`/`envs\\tts` fully provisioned
(`scripts/setup_windows.ps1`), model weights downloaded
(`models/MODELS.md`), and either a GPU or patience for a CPU fallback.

Run locally with:
    scripts\\run_gpu_tests.ps1
or directly:
    .venv\\Scripts\\pytest -m "gpu or ollama" tests/gpu -v

See docs/qa/test-plan.md's RT-# table for what each test corresponds to,
and docs/ops/installation-deployment.md for provisioning these venvs.
Every test here is self-skipping (not failing) if its prerequisite
(venv/weights/presenter asset/Ollama) isn't present, so a partially
-provisioned machine still gets useful signal from the tests it can run.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from echoface.util.ffmpeg import ffmpeg_available, probe, run_ffmpeg
from echoface.util.gpu import ollama_reachable

pytestmark = pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg/ffprobe not on PATH")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FACE_PYTHON = REPO_ROOT / "envs" / "face" / "Scripts" / "python.exe"
TTS_PYTHON = REPO_ROOT / "envs" / "tts" / "Scripts" / "python.exe"
REALTEST_PORTRAIT = REPO_ROOT / "assets" / "portraits" / "realtest" / "portrait.png"
WAV2LIP_CKPT = REPO_ROOT / "models" / "wav2lip" / "wav2lip_gan.pth"
GFPGAN_CKPT = REPO_ROOT / "models" / "gfpgan" / "GFPGANv1.4.pth"
CODEFORMER_CKPT = REPO_ROOT / "models" / "codeformer" / "codeformer.pth"
PIPER_MODEL = REPO_ROOT / "models" / "piper" / "en_US-lessac-medium.onnx"
PIPER_EXE = REPO_ROOT / "envs" / "tts" / "Scripts" / "piper.exe"


def _require(*paths: Path, reason: str) -> None:
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        pytest.skip(f"{reason} (missing: {', '.join(missing)})")


@pytest.fixture
def tiny_audio(tmp_path) -> Path:
    """~1s of real-ish audio (not silence — Wav2Lip/whisper need signal)."""
    p = tmp_path / "tiny_voice_16k.wav"
    run_ffmpeg(["-f", "lavfi", "-i", "sine=frequency=220:duration=1.2:sample_rate=16000", "-ac", "1", str(p)])
    return p


@pytest.mark.gpu
@pytest.mark.slow
def test_real_wav2lip_tiny_render(tiny_audio, tmp_path):
    """Real Wav2Lip inference (scripts/wav2lip_runner.py) on a 1.2s clip
    against the realtest presenter's real, detectable face — corresponds
    to test-plan.md RT-3 but with a minimal input for CI-adjacent speed."""
    _require(
        FACE_PYTHON,
        WAV2LIP_CKPT,
        REALTEST_PORTRAIT,
        reason="envs\\face / Wav2Lip weights / realtest portrait not provisioned",
    )
    out_path = tmp_path / "tiny_face.mp4"
    cache_file = tmp_path / "facecache.json"
    import subprocess

    result = subprocess.run(
        [
            str(FACE_PYTHON),
            "scripts/wav2lip_runner.py",
            "--checkpoint_path",
            str(WAV2LIP_CKPT),
            "--face",
            str(REALTEST_PORTRAIT),
            "--audio",
            str(tiny_audio),
            "--outfile",
            str(out_path),
            "--pads",
            "0",
            "15",
            "0",
            "0",
            "--face_det_batch_size",
            "4",
            "--wav2lip_batch_size",
            "4",
            "--resize_factor",
            "1",
            "--device",
            "cuda",
            "--nosmooth",
            "--cache_file",
            str(cache_file),
            "--cache_key",
            "gpu-test-realtest",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert out_path.exists()
    info = probe(out_path)
    assert info.has_video and info.has_audio
    assert cache_file.exists()  # real face-box cache was written


@pytest.mark.gpu
@pytest.mark.slow
def test_real_gfpgan_restoration_tiny(tmp_path):
    """Real GFPGAN restoration (scripts/gfpgan_runner.py) on a handful of
    frames — corresponds to test-plan.md RT-3's restore step."""
    _require(
        FACE_PYTHON,
        GFPGAN_CKPT,
        REALTEST_PORTRAIT,
        reason="envs\\face / GFPGAN weights / realtest portrait not provisioned",
    )
    src = tmp_path / "tiny_src.mp4"
    run_ffmpeg(
        ["-loop", "1", "-i", str(REALTEST_PORTRAIT), "-t", "0.5", "-r", "5", "-pix_fmt", "yuv420p", str(src)]
    )
    out_path = tmp_path / "tiny_restored.mp4"
    import subprocess

    result = subprocess.run(
        [
            str(FACE_PYTHON),
            "scripts/gfpgan_runner.py",
            "--input",
            str(src),
            "--outfile",
            str(out_path),
            "--model_path",
            str(GFPGAN_CKPT),
            "--device",
            "cuda",
            "--region",
            "face",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert out_path.exists()
    assert probe(out_path).has_video


@pytest.mark.gpu
@pytest.mark.slow
def test_real_codeformer_restoration_tiny_mouth_region(tmp_path):
    """Real CodeFormer restoration with --region mouth on a handful of
    frames — corresponds to test-plan.md RT-10 (CodeFormer)."""
    _require(
        FACE_PYTHON,
        CODEFORMER_CKPT,
        REALTEST_PORTRAIT,
        reason="envs\\face / CodeFormer weights / realtest portrait not provisioned",
    )
    src = tmp_path / "tiny_src.mp4"
    run_ffmpeg(
        ["-loop", "1", "-i", str(REALTEST_PORTRAIT), "-t", "0.5", "-r", "5", "-pix_fmt", "yuv420p", str(src)]
    )
    out_path = tmp_path / "tiny_restored.mp4"
    import subprocess

    result = subprocess.run(
        [
            str(FACE_PYTHON),
            "scripts/codeformer_runner.py",
            "--input",
            str(src),
            "--outfile",
            str(out_path),
            "--model_path",
            str(CODEFORMER_CKPT),
            "--device",
            "cuda",
            "--region",
            "mouth",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert out_path.exists()
    assert probe(out_path).has_video


@pytest.mark.gpu
@pytest.mark.slow
def test_real_piper_synthesis_tiny(tmp_path):
    """Real Piper TTS synthesis — corresponds to test-plan.md RT-2."""
    _require(PIPER_EXE, PIPER_MODEL, reason="envs\\tts / Piper voice model not provisioned")
    out_path = tmp_path / "tiny_voice.wav"
    import subprocess

    result = subprocess.run(
        [str(PIPER_EXE), "-m", str(PIPER_MODEL), "-f", str(out_path), "--length-scale", "1.0"],
        input="This is a real Piper test.",
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert out_path.exists()
    info = probe(out_path)
    assert info.has_audio
    assert info.duration_s > 0.5


@pytest.mark.ollama
@pytest.mark.slow
def test_real_ollama_script_generation():
    """Real Ollama call through the full ScriptStage — corresponds to
    test-plan.md RT-1. Skips (not fails) if Ollama isn't reachable or the
    configured model isn't pulled."""
    from echoface.config import load_config
    from echoface.job import Job
    from echoface.stages.script import ScriptStage
    from echoface.util.gpu import ollama_models

    cfg = load_config()
    if not ollama_reachable(cfg.script.host, timeout=3):
        pytest.skip(f"Ollama not reachable at {cfg.script.host}")
    models = ollama_models(cfg.script.host)
    if not any(cfg.script.model in m for m in models):
        pytest.skip(f"Ollama model {cfg.script.model!r} not pulled")

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        job = Job.create(topic="gpu-test topic", root=Path(tmp), job_id="gpu-test-script")
        stage = ScriptStage(job, cfg, topic="three quick habits for focus")
        stage.run()
        script_path = job.path_for("script.json")
        assert script_path.exists()
        import json

        data = json.loads(script_path.read_text(encoding="utf-8"))
        assert data["hook"]
        assert data["lines"]


def teardown_module(module):
    # Best-effort cleanup of any facecache.json this test session wrote
    # under a tmp_path (pytest handles tmp_path cleanup itself; this is
    # just defensive for cache files written relative to cwd, if any).
    stray = REPO_ROOT / "facecache.json"
    if stray.exists():
        shutil.rmtree(stray, ignore_errors=True)
