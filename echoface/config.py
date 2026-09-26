"""Config loading and validation (pydantic) + per-stage config hashing."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator


class ScriptConfig(BaseModel):
    engine: str = "ollama"  # ollama | file
    model: str = "qwen2.5:7b"
    template: str = "prompts/short_default.md"
    temperature: float = 0.7
    host: str = "http://localhost:11434"
    max_retries: int = 3

    @field_validator("engine")
    @classmethod
    def _check_engine(cls, v: str) -> str:
        if v not in ("ollama", "file"):
            raise ValueError(f"script.engine must be 'ollama' or 'file', got {v!r}")
        return v


class VoiceConfig(BaseModel):
    engine: str = "piper"  # piper | xtts | dummy
    piper_exe: str = "envs/tts/Scripts/piper.exe"
    piper_model: str = "models/piper/en_US-lessac-medium.onnx"
    speed: float = 1.05
    pause_ms: int = 350
    xtts_speaker_wav: str | None = None

    @field_validator("engine")
    @classmethod
    def _check_engine(cls, v: str) -> str:
        if v not in ("piper", "xtts", "dummy"):
            raise ValueError(f"voice.engine must be 'piper', 'xtts' or 'dummy', got {v!r}")
        return v


class FaceConfig(BaseModel):
    engine: str = "wav2lip"  # wav2lip | sadtalker | dummy
    source: str = "idle"  # idle | photo
    restore: str = "none"  # none | gfpgan | codeformer
    restore_region: str = "face"  # face | mouth — see echoface.util.restore_blend
    batch_size: int = 32
    face_det_batch_size: int = 4
    device: str = "auto"  # auto | cuda | cpu
    resize_factor: int = 1
    pads: list[int] = Field(default_factory=lambda: [0, 15, 0, 0])
    chunk_seconds: float = 40.0

    @field_validator("engine")
    @classmethod
    def _check_engine(cls, v: str) -> str:
        if v not in ("wav2lip", "sadtalker", "dummy"):
            raise ValueError(f"face.engine must be 'wav2lip', 'sadtalker' or 'dummy', got {v!r}")
        return v

    @field_validator("restore")
    @classmethod
    def _check_restore(cls, v: str) -> str:
        if v not in ("none", "gfpgan", "codeformer"):
            raise ValueError(f"face.restore must be 'none', 'gfpgan' or 'codeformer', got {v!r}")
        return v

    @field_validator("restore_region")
    @classmethod
    def _check_restore_region(cls, v: str) -> str:
        if v not in ("face", "mouth"):
            raise ValueError(f"face.restore_region must be 'face' or 'mouth', got {v!r}")
        return v

    @field_validator("device")
    @classmethod
    def _check_device(cls, v: str) -> str:
        if v not in ("auto", "cuda", "cpu"):
            raise ValueError(f"face.device must be 'auto', 'cuda' or 'cpu', got {v!r}")
        return v


class CaptionsConfig(BaseModel):
    engine: str = "whisper"  # whisper | dummy
    model: str = "small"
    device: str = "cpu"
    compute_type: str = "int8"
    style: str = "bold_center"
    max_words_per_line: int = 3
    font: str = "Arial"
    font_size: int = 96

    @field_validator("engine")
    @classmethod
    def _check_engine(cls, v: str) -> str:
        if v not in ("whisper", "dummy"):
            raise ValueError(f"captions.engine must be 'whisper' or 'dummy', got {v!r}")
        return v


class ComposeConfig(BaseModel):
    width: int = 1080
    height: int = 1920
    fps: int = 30
    layout: str = "face_top"  # face_top | full_face | face_bottom
    background: str | None = None
    background_color: str = "0x101018"
    music: str | None = None
    music_volume_db: float = -20.0
    duck_under_voice: bool = True
    loudness_lufs: float = -14.0
    # loudnorm TP target on the pre-encode PCM. Spec requires the FINAL
    # deliverable's true peak <= -1 dBTP; lossy AAC re-encoding measurably
    # overshoots the source PCM's true peak (observed +0.1 to +1.1 dB on
    # this machine's real renders), so the pre-encode target is set lower
    # than -1 to leave margin — see build_loudnorm_filter's docstring and
    # README's "Real end-to-end verification" section for the evidence.
    true_peak_dbtp: float = -2.5
    loudness_lra: float = 11.0  # loudnorm LRA (loudness range) target
    pre_limiter_dbfs: float = -9.0  # premix alimiter ceiling before loudnorm (see ADR-0004/0009)
    loudness_tolerance_lu: float = 0.5  # acceptable |measured - target| on the FINAL encoded file
    loudness_hard_tp_ceiling_dbtp: float = (
        -1.0
    )  # spec's actual final-file requirement (stricter than true_peak_dbtp's pre-encode margin)
    loudness_max_encode_attempts: int = 2  # 1 initial + up to (n-1) corrective re-encodes
    crf: int = 19
    disclosure_line: str = "Presenter is AI-generated."

    @field_validator("layout")
    @classmethod
    def _check_layout(cls, v: str) -> str:
        if v not in ("face_top", "full_face", "face_bottom"):
            raise ValueError(f"compose.layout must be one of face_top/full_face/face_bottom, got {v!r}")
        return v


class PruneConfig(BaseModel):
    older_than: str = "30d"  # parsed by echoface.prune.parse_duration
    keep_final: bool = True  # keep final.mp4/metadata.json, remove intermediates only


class EchofaceConfig(BaseModel):
    presenter: str = "anchor1"
    language: str = "en"
    target_seconds: int = 35
    monetized: bool = False

    script: ScriptConfig = Field(default_factory=ScriptConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    face: FaceConfig = Field(default_factory=FaceConfig)
    captions: CaptionsConfig = Field(default_factory=CaptionsConfig)
    compose: ComposeConfig = Field(default_factory=ComposeConfig)
    prune: PruneConfig = Field(default_factory=PruneConfig)

    def stage_config(self, stage_name: str) -> dict:
        mapping = {
            "script": self.script,
            "voice": self.voice,
            "face": self.face,
            "captions": self.captions,
            "compose": self.compose,
        }
        model = mapping[stage_name]
        return model.model_dump()


DEFAULT_CONFIG_PATH = Path("config/echoface.yaml")


# Environment-variable overrides for machine-specific / secret-shaped
# values, applied after yaml but before CLI overrides (CLI flag > env var
# > yaml > pydantic defaults — an explicit `--flag` on the command line is
# the most specific, most deliberate signal, so it wins over a .env value
# that might be a stale/forgotten machine default; see ADR-0008).
# See .env.example for documentation of each. Keeping this list short and
# explicit (rather than a generic "any dotted config key as env var"
# mechanism) makes every override visible in one place.
_ENV_OVERRIDES = {
    "ECHOFACE_OLLAMA_HOST": ("script", "host"),
    "ECHOFACE_OLLAMA_MODEL": ("script", "model"),
    "ECHOFACE_PIPER_EXE": ("voice", "piper_exe"),
    "ECHOFACE_PIPER_MODEL": ("voice", "piper_model"),
    "ECHOFACE_FFMPEG_PATH": ("_ffmpeg_path",),  # consumed by util.ffmpeg, not a pydantic field
}


def _apply_env_overrides(data: dict) -> dict:
    result = dict(data)
    for env_name, key_path in _ENV_OVERRIDES.items():
        value = os.environ.get(env_name)
        if value is None:
            continue
        if key_path[0] == "_ffmpeg_path":
            continue  # handled directly by util.ffmpeg via os.environ, not part of the config model
        section, field = key_path
        result[section] = dict(result.get(section) or {})
        result[section][field] = value
    return result


def load_config(path: Path | None = None, overrides: dict | None = None) -> EchofaceConfig:
    """Load YAML config, apply environment-variable overrides, apply CLI
    overrides (dotted-flat dict of top-level keys) last, and validate with
    pydantic. Precedence: CLI flag > env var (.env) > config/*.yaml >
    pydantic field defaults — see ADR-0008."""
    path = path or DEFAULT_CONFIG_PATH
    data: dict = {}
    if path and Path(path).exists():
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    data = _apply_env_overrides(data)
    if overrides:
        data = _deep_merge(data, overrides)
    return EchofaceConfig.model_validate(data)


def _deep_merge(base: dict, overrides: dict) -> dict:
    result = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        elif value is not None:
            result[key] = value
    return result


def config_hash(payload: dict) -> str:
    """Stable sha256 hash of a JSON-serialisable dict (order-independent)."""
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def stage_hash(cfg: EchofaceConfig, stage_name: str, extra: dict | None = None) -> str:
    """Compute the hash used to decide whether a stage needs to re-run.

    Includes the stage's own config subset plus any globally-relevant
    fields (presenter, language, target_seconds) and any stage-specific
    "extra" inputs (e.g. topic text, upstream content hash).
    """
    payload = {
        "stage": stage_config_dict(cfg, stage_name),
        "presenter": cfg.presenter,
        "language": cfg.language,
        "target_seconds": cfg.target_seconds,
    }
    if extra:
        payload["extra"] = extra
    return config_hash(payload)


def stage_config_dict(cfg: EchofaceConfig, stage_name: str) -> dict:
    return cfg.stage_config(stage_name)
