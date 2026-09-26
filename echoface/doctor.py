"""`echoface doctor`: environment checks. Must never crash even when
everything is missing -- every check is wrapped and reports red/green.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from echoface.config import EchofaceConfig
from echoface.util.ffmpeg import ffmpeg_available, ffmpeg_exe
from echoface.util.gpu import detect_gpu, ollama_models, ollama_reachable


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""
    level: str = "error"  # error | warning


def _check_nvidia_smi() -> Check:
    gpu = detect_gpu()
    if gpu.available:
        return Check(
            "nvidia-smi / GPU", True, f"{gpu.name} (driver {gpu.driver_version}, {gpu.memory_total_mb} MB)"
        )
    return Check("nvidia-smi / GPU", False, gpu.error or "no NVIDIA GPU detected", level="warning")


def _check_ffmpeg() -> Check:
    if ffmpeg_available():
        exe = ffmpeg_exe()
        try:
            result = subprocess.run([exe, "-version"], capture_output=True, text=True, timeout=5)
            first_line = result.stdout.splitlines()[0] if result.stdout else ""
        except Exception:
            first_line = ""
        return Check("ffmpeg / ffprobe", True, first_line)
    return Check("ffmpeg / ffprobe", False, "ffmpeg and/or ffprobe not found on PATH")


def _doctor_timeout() -> float:
    """How long doctor waits on each network probe (Ollama reachability /
    model list). Configurable via ECHOFACE_DOCTOR_TIMEOUT_S — the default
    of 3s occasionally reads as a false "not reachable" on a machine under
    heavy load (e.g. right after a big test run still holding CPU/IO), so
    a slower machine or CI runner can raise it without a code change."""
    raw = os.environ.get("ECHOFACE_DOCTOR_TIMEOUT_S")
    if raw:
        try:
            return float(raw)
        except ValueError:
            pass
    return 3.0


def _check_ollama(cfg: EchofaceConfig) -> Check:
    timeout = _doctor_timeout()
    if ollama_reachable(cfg.script.host, timeout=timeout):
        models = ollama_models(cfg.script.host, timeout=timeout)
        wanted = cfg.script.model
        if any(wanted in m for m in models):
            return Check("Ollama", True, f"reachable, model {wanted!r} present ({len(models)} models total)")
        return Check(
            "Ollama",
            False,
            f"reachable, but model {wanted!r} not pulled (run: ollama pull {wanted})",
            level="warning",
        )
    return Check(
        "Ollama", False, f"not reachable at {cfg.script.host} (is `ollama serve` running?)", level="warning"
    )


def _check_venv(path: Path, label: str) -> Check:
    py = path / "Scripts" / "python.exe"
    if py.exists():
        return Check(label, True, str(py))
    return Check(label, False, f"{py} not found (run scripts/setup_windows.ps1)", level="warning")


def _check_torch_cuda(face_env: Path) -> Check:
    py = face_env / "Scripts" / "python.exe"
    if not py.exists():
        return Check("torch/CUDA in envs\\face", False, "envs\\face venv not found", level="warning")
    try:
        result = subprocess.run(
            [str(py), "-c", "import torch;print(torch.__version__, torch.cuda.is_available())"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return Check("torch/CUDA in envs\\face", True, result.stdout.strip())
        return Check("torch/CUDA in envs\\face", False, "torch not importable in envs\\face", level="warning")
    except Exception as exc:  # pragma: no cover - environment dependent
        return Check("torch/CUDA in envs\\face", False, str(exc), level="warning")


def _check_model_files(cfg: EchofaceConfig) -> list[Check]:
    checks = []
    piper_model = Path(cfg.voice.piper_model)
    if cfg.voice.engine == "piper":
        ok = piper_model.exists()
        checks.append(Check(f"Piper model ({piper_model})", ok, "" if ok else "not found", level="warning"))
    if cfg.face.engine == "wav2lip":
        wav2lip_ckpt = Path("models/wav2lip/wav2lip_gan.pth")
        ok = wav2lip_ckpt.exists()
        checks.append(
            Check(f"Wav2Lip checkpoint ({wav2lip_ckpt})", ok, "" if ok else "not found", level="warning")
        )
    if cfg.face.engine == "sadtalker":
        st_ckpt = Path("vendor/SadTalker/checkpoints/SadTalker_V0.0.2_256.safetensors")
        ok = st_ckpt.exists()
        checks.append(
            Check(f"SadTalker checkpoint ({st_ckpt})", ok, "" if ok else "not found", level="warning")
        )
    if cfg.face.restore == "gfpgan":
        gfpgan_ckpt = Path("models/gfpgan/GFPGANv1.4.pth")
        ok = gfpgan_ckpt.exists()
        checks.append(
            Check(f"GFPGAN checkpoint ({gfpgan_ckpt})", ok, "" if ok else "not found", level="warning")
        )
    return checks


def _check_presenters(cfg: EchofaceConfig) -> list[Check]:
    checks = []
    portraits_root = Path("assets/portraits")
    if not portraits_root.exists():
        checks.append(Check("presenters", False, "assets/portraits not found", level="warning"))
        return checks
    from echoface.job import ConsentError, check_presenter_consent

    for presenter_dir in sorted(p for p in portraits_root.iterdir() if p.is_dir()):
        try:
            check_presenter_consent(presenter_dir.name, portraits_root)
            checks.append(Check(f"presenter '{presenter_dir.name}' consent", True))
        except ConsentError as exc:
            checks.append(
                Check(f"presenter '{presenter_dir.name}' consent", False, str(exc), level="warning")
            )
    return checks


def _check_monetization_licence(cfg: EchofaceConfig) -> Check | None:
    if not cfg.monetized:
        return None
    non_commercial_engines = {"wav2lip": "Wav2Lip (wav2lip_gan.pth) is research/non-commercial licensed"}
    if cfg.face.engine in non_commercial_engines:
        return Check(
            "monetization licence check",
            False,
            f"monetized=true but face.engine={cfg.face.engine!r}: {non_commercial_engines[cfg.face.engine]}. "
            "See models/MODELS.md and confirm commercial terms before monetising.",
            level="warning",
        )
    return Check("monetization licence check", True, "no known non-commercial models selected")


def run_doctor(cfg: EchofaceConfig) -> list[Check]:
    checks: list[Check] = []
    checks.append(_check_ffmpeg())
    checks.append(_check_nvidia_smi())
    checks.append(_check_ollama(cfg))
    checks.append(_check_venv(Path(".venv"), "orchestrator venv (.venv)"))
    checks.append(_check_venv(Path("envs/face"), "envs\\face venv"))
    checks.append(_check_venv(Path("envs/tts"), "envs\\tts venv"))
    checks.append(_check_torch_cuda(Path("envs/face")))
    checks.extend(_check_model_files(cfg))
    checks.extend(_check_presenters(cfg))
    mon_check = _check_monetization_licence(cfg)
    if mon_check:
        checks.append(mon_check)
    return checks
