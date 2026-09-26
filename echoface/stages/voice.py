"""Voice stage: script.json -> voice.wav (+ voice_16k.wav copy).

Engines: piper (default CLI subprocess), xtts (M8, envs\\tts subprocess),
dummy (generates a sine-wave placeholder for tests/smoke without a real
TTS engine installed).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from echoface.stages.base import Stage
from echoface.util import ffmpeg as ffm
from echoface.util.proc import resolve_exe
from echoface.util.text import normalize_for_speech, word_count

WORDS_PER_SECOND_ESTIMATE = 2.6


class VoiceEngineError(RuntimeError):
    pass


def script_segments(script: dict) -> list[str]:
    """Return the ordered list of spoken segments (hook, lines..., cta)."""
    segments = [script["hook"], *script.get("lines", []), script["cta"]]
    return [normalize_for_speech(s) for s in segments if s and s.strip()]


class VoiceEngine:
    def synth_segment(self, text: str, out_wav: Path) -> None:
        raise NotImplementedError


class PiperVoiceEngine(VoiceEngine):
    def __init__(self, piper_exe: str, model_path: str, speed: float = 1.0):
        self.piper_exe = piper_exe
        self.model_path = model_path
        self.speed = speed

    def synth_segment(self, text: str, out_wav: Path) -> None:
        exe = shutil.which(self.piper_exe) or resolve_exe(self.piper_exe)
        length_scale = 1.0 / self.speed if self.speed else 1.0
        # piper-tts >= 1.8 CLI (pip package, replaces the old rhasspy C++
        # piper.exe binary): flags are -m/-c/-f and --length-scale (hyphen,
        # not underscore); config (.onnx.json) auto-detects next to the
        # model if -c is omitted, but we pass it explicitly for clarity.
        cmd = [
            exe,
            "-m",
            self.model_path,
            "-c",
            f"{self.model_path}.json",
            "-f",
            str(out_wav),
            "--length-scale",
            str(length_scale),
        ]
        try:
            subprocess.run(cmd, input=text, text=True, check=True, capture_output=True)
        except FileNotFoundError as exc:
            raise VoiceEngineError(
                f"piper executable not found ({self.piper_exe!r}); install it in envs\\tts "
                "or set voice.engine: dummy for testing"
            ) from exc
        except subprocess.CalledProcessError as exc:
            raise VoiceEngineError(f"piper failed: {exc.stderr}") from exc


class XttsVoiceEngine(VoiceEngine):
    """M8: runs XTTS v2 inside envs\\tts via a small runner script."""

    def __init__(self, python_exe: str = "envs/tts/Scripts/python.exe", speaker_wav: str | None = None):
        self.python_exe = python_exe
        self.speaker_wav = speaker_wav

    def synth_segment(self, text: str, out_wav: Path) -> None:
        runner = Path(__file__).resolve().parent.parent.parent / "scripts" / "xtts_runner.py"
        cmd = [resolve_exe(self.python_exe), str(runner), "--text", text, "--out", str(out_wav)]
        if self.speaker_wav:
            cmd += ["--speaker_wav", self.speaker_wav]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            raise VoiceEngineError(f"xtts synth failed: {exc}") from exc


class DummyVoiceEngine(VoiceEngine):
    """Generates a sine-wave tone whose duration approximates natural speech
    for the given text, using ffmpeg's lavfi source. No network, no model
    files — used for smoke tests and CI."""

    def synth_segment(self, text: str, out_wav: Path) -> None:
        n_words = max(word_count(text), 1)
        duration = max(n_words / WORDS_PER_SECOND_ESTIMATE, 0.3)
        cmd = [
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=220:duration={duration:.3f}:sample_rate=22050",
            "-ac",
            "1",
            str(out_wav),
        ]
        ffm.run_ffmpeg(cmd)


def build_engine(cfg) -> VoiceEngine:
    if cfg.engine == "piper":
        return PiperVoiceEngine(cfg.piper_exe, cfg.piper_model, cfg.speed)
    if cfg.engine == "xtts":
        return XttsVoiceEngine(speaker_wav=cfg.xtts_speaker_wav)
    if cfg.engine == "dummy":
        return DummyVoiceEngine()
    raise VoiceEngineError(f"unknown voice engine {cfg.engine!r}")


def concat_with_pauses(
    segment_wavs: list[Path], pause_ms: int, out_wav: Path, sample_rate: int = 22050
) -> None:
    """Concatenate segment WAVs with a silence gap between them using the
    ffmpeg concat filter (avoids intermediate files beyond a filter list)."""
    if not segment_wavs:
        raise VoiceEngineError("no voice segments to concatenate")
    pause_s = max(pause_ms, 0) / 1000.0

    inputs: list[str] = []
    filter_parts: list[str] = []
    concat_labels: list[str] = []
    sil_idx = 0  # unique label suffix for generated silence segments
    for i, seg in enumerate(segment_wavs):
        # i doubles as the -i input index for [N:a] references, since
        # exactly one -i is added per segment in this same loop.
        inputs += ["-i", str(seg)]
        filter_parts.append(f"[{i}:a]anull[a{i}]")
        concat_labels.append(f"[a{i}]")
        if i != len(segment_wavs) - 1 and pause_s > 0:
            filter_parts.append(f"anullsrc=r={sample_rate}:cl=mono:d={pause_s:.3f}[sil{sil_idx}]")
            concat_labels.append(f"[sil{sil_idx}]")
            sil_idx += 1

    n = len(concat_labels)
    filter_parts.append("".join(concat_labels) + f"concat=n={n}:v=0:a=1[out]")
    filter_complex = ";".join(filter_parts)

    cmd = [*inputs, "-filter_complex", filter_complex, "-map", "[out]", "-ar", str(sample_rate), str(out_wav)]
    ffm.run_ffmpeg(cmd)


def postprocess_voice(raw_wav: Path, final_wav: Path, wav16k: Path) -> None:
    """Trim leading/trailing silence and peak-normalise into final_wav, then
    create a 16 kHz mono copy for the face stage."""
    ffm.run_ffmpeg(
        [
            "-i",
            str(raw_wav),
            "-af",
            "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.1:"
            "detection=peak,areverse,"
            "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.1:"
            "detection=peak,areverse,"
            "dynaudnorm=p=0.95:m=10",
            str(final_wav),
        ]
    )
    ffm.run_ffmpeg(["-i", str(final_wav), "-ar", "16000", "-ac", "1", str(wav16k)])


class VoiceStage(Stage):
    name = "voice"

    def inputs(self) -> list[Path]:
        return [self.job.path_for("script.json")]

    def outputs(self) -> list[Path]:
        return [self.job.path_for("voice.wav"), self.job.path_for("voice_16k.wav")]

    def run(self) -> None:
        script_path = self.job.path_for("script.json")
        with open(script_path, encoding="utf-8") as fh:
            script = json.load(fh)
        segments = script_segments(script)
        engine = build_engine(self.cfg.voice)

        with tempfile.TemporaryDirectory(prefix="echoface_voice_") as tmpdir:
            tmp = Path(tmpdir)
            seg_paths = []
            for i, text in enumerate(segments):
                seg_path = tmp / f"seg_{i:03d}.wav"
                engine.synth_segment(text, seg_path)
                seg_paths.append(seg_path)

            raw_concat = tmp / "concat.wav"
            concat_with_pauses(seg_paths, self.cfg.voice.pause_ms, raw_concat)

            final_wav = self.job.path_for("voice.wav")
            wav16k = self.job.path_for("voice_16k.wav")
            final_wav.parent.mkdir(parents=True, exist_ok=True)
            postprocess_voice(raw_concat, final_wav, wav16k)
