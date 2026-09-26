"""GPU / CUDA detection and Ollama VRAM-unload helpers.

The orchestrator venv does NOT have torch installed (torch lives in
envs\\face). CUDA availability here is therefore probed via ``nvidia-smi``
(driver-level) rather than ``torch.cuda.is_available()``; the face-stage
subprocess (running inside envs\\face) is responsible for the authoritative
torch-level check and for its own CPU fallback on OOM.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

import requests


@dataclass
class GpuInfo:
    nvidia_smi_found: bool
    name: str | None = None
    driver_version: str | None = None
    memory_total_mb: int | None = None
    error: str | None = None

    @property
    def available(self) -> bool:
        return self.nvidia_smi_found and self.error is None


def detect_gpu(timeout: float = 5.0) -> GpuInfo:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return GpuInfo(nvidia_smi_found=False, error="nvidia-smi not found on PATH")
    try:
        result = subprocess.run(
            [
                exe,
                "--query-gpu=name,driver_version,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except Exception as exc:  # pragma: no cover - environment dependent
        return GpuInfo(nvidia_smi_found=True, error=str(exc))

    if result.returncode != 0:
        return GpuInfo(nvidia_smi_found=True, error=result.stderr.strip() or "nvidia-smi failed")

    line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
    parts = [p.strip() for p in line.split(",")]
    if len(parts) < 3:
        return GpuInfo(nvidia_smi_found=True, error=f"unexpected nvidia-smi output: {line!r}")
    name, driver, mem = parts[0], parts[1], parts[2]
    try:
        mem_mb = int(float(mem))
    except ValueError:  # pragma: no cover
        mem_mb = None
    return GpuInfo(nvidia_smi_found=True, name=name, driver_version=driver, memory_total_mb=mem_mb)


def unload_ollama_model(model: str, host: str = "http://localhost:11434", timeout: float = 10.0) -> bool:
    """Ask Ollama to unload a model from VRAM immediately (keep_alive=0).

    Returns True on success, False if Ollama is unreachable or the request
    failed (never raises — this is a best-effort courtesy call before the
    face stage claims the GPU).
    """
    try:
        resp = requests.post(
            f"{host.rstrip('/')}/api/generate",
            json={"model": model, "prompt": "", "keep_alive": 0},
            timeout=timeout,
        )
        return resp.status_code == 200
    except requests.RequestException:
        return False


def ollama_reachable(host: str = "http://localhost:11434", timeout: float = 3.0) -> bool:
    try:
        resp = requests.get(f"{host.rstrip('/')}/api/tags", timeout=timeout)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def ollama_models(host: str = "http://localhost:11434", timeout: float = 3.0) -> list[str]:
    try:
        resp = requests.get(f"{host.rstrip('/')}/api/tags", timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return [m.get("name", "") for m in data.get("models", [])]
    except requests.RequestException:
        return []
