"""FFmpeg/ffprobe helpers: probing, path escaping, filtergraph construction,
audio chunk/loop planning. Kept dependency-free (stdlib + subprocess only)
so it is fully unit-testable without a GPU or heavy models.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class FfmpegNotFound(RuntimeError):
    pass


def ffmpeg_exe() -> str:
    """Resolve the ffmpeg binary: ECHOFACE_FFMPEG_PATH env var (if set,
    e.g. a non-PATH install) takes priority over PATH lookup."""
    override = os.environ.get("ECHOFACE_FFMPEG_PATH")
    if override:
        return str(Path(override) / "ffmpeg.exe") if Path(override).is_dir() else override
    exe = shutil.which("ffmpeg")
    if not exe:
        raise FfmpegNotFound("ffmpeg not found on PATH (set ECHOFACE_FFMPEG_PATH to override)")
    return exe


def ffprobe_exe() -> str:
    """Resolve the ffprobe binary: ECHOFACE_FFMPEG_PATH env var (if set)
    takes priority over PATH lookup, same convention as ffmpeg_exe()."""
    override = os.environ.get("ECHOFACE_FFMPEG_PATH")
    if override:
        return (
            str(Path(override) / "ffprobe.exe")
            if Path(override).is_dir()
            else override.replace("ffmpeg", "ffprobe")
        )
    exe = shutil.which("ffprobe")
    if not exe:
        raise FfmpegNotFound("ffprobe not found on PATH (set ECHOFACE_FFMPEG_PATH to override)")
    return exe


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


@dataclass
class MediaInfo:
    duration_s: float
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    has_audio: bool = False
    has_video: bool = False


def probe(path: Path) -> MediaInfo:
    exe = ffprobe_exe()
    cmd = [
        exe,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    fmt = data.get("format", {})
    duration = float(fmt.get("duration", 0.0) or 0.0)
    width = height = None
    fps = None
    has_audio = has_video = False
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video" and width is None:
            width = stream.get("width")
            height = stream.get("height")
            has_video = True
            rate = stream.get("r_frame_rate", "0/1")
            try:
                num, den = rate.split("/")
                fps = float(num) / float(den) if float(den) else None
            except (ValueError, ZeroDivisionError):
                fps = None
            if not duration:
                duration = float(stream.get("duration", 0.0) or 0.0)
        elif stream.get("codec_type") == "audio":
            has_audio = True
            if not duration:
                duration = float(stream.get("duration", 0.0) or 0.0)
    return MediaInfo(
        duration_s=duration, width=width, height=height, fps=fps, has_audio=has_audio, has_video=has_video
    )


def escape_filter_path(path: Path) -> str:
    """Escape a filesystem path for use inside an ffmpeg filtergraph string
    (e.g. the ``subtitles``/``ass`` filter's filename argument), handling
    the Windows drive-letter colon and backslashes correctly.

    ffmpeg filter argument escaping rules: backslash and colon are special
    inside a filter's option value, and the whole graph is often further
    wrapped in single quotes on the shell. We escape for the *filtergraph*
    level (backslashes doubled, colon escaped with a backslash), then wrap
    in single quotes, which is the combination that reliably survives both
    ``subprocess`` argv passing (no shell) and the ffmpeg filter parser.
    """
    p = str(path).replace("\\", "/")
    # ffmpeg filter parser: escape ':' -> '\:' and "'" -> "\\\\'" (rare).
    # Also re-escape backslashes if any remain (e.g. UNC paths) before colon.
    p = p.replace(":", "\\:")
    return f"'{p}'"


def build_ping_pong_plan(clip_duration_s: float, target_duration_s: float) -> list[tuple[str, float]]:
    """Plan a ping-pong (forward/reverse) loop of a short idle clip to cover
    a longer audio duration.

    Returns a list of (direction, duration_s) segments, alternating
    "forward"/"reverse", whose durations sum to >= target_duration_s (the
    caller trims the final concatenated video down to target_duration_s).
    Returns an empty list if the clip already covers the target.
    """
    if clip_duration_s <= 0:
        raise ValueError("clip_duration_s must be > 0")
    if clip_duration_s >= target_duration_s:
        return []
    segments: list[tuple[str, float]] = []
    covered = 0.0
    forward = True
    while covered < target_duration_s:
        segments.append(("forward" if forward else "reverse", clip_duration_s))
        covered += clip_duration_s
        forward = not forward
    return segments


def build_chunk_plan(total_duration_s: float, chunk_seconds: float = 40.0) -> list[tuple[float, float]]:
    """Split a long audio duration into (start, duration) chunks no longer
    than ``chunk_seconds`` each, for the face stage. Returns a single chunk
    covering the whole duration if it already fits.
    """
    if total_duration_s <= 0:
        raise ValueError("total_duration_s must be > 0")
    if total_duration_s <= chunk_seconds:
        return [(0.0, total_duration_s)]
    n_chunks = math.ceil(total_duration_s / chunk_seconds)
    chunk_len = total_duration_s / n_chunks
    chunks = []
    start = 0.0
    for i in range(n_chunks):
        dur = chunk_len if i < n_chunks - 1 else (total_duration_s - start)
        chunks.append((start, dur))
        start += chunk_len
    return chunks


LAYOUTS = ("face_top", "full_face", "face_bottom")


def build_audio_premix_filtergraph(
    *,
    has_music: bool,
    duck_under_voice: bool,
    music_volume_db: float,
    voice_input_idx: int = 0,
    music_input_idx: int = 1,
    pre_limiter_db: float | None = -9.0,
) -> dict:
    """Build the voice+music mixing/ducking part of the audio graph, ending
    in a single ``[premix]`` output label (no loudnorm — that's applied
    separately, see ``build_loudnorm_filter``).

    ``pre_limiter_db``: a fast true-peak limiter applied last, before
    ``[premix]``, ceiling in dBFS (None disables it). This matters for
    voice.wav specifically: echoface's voice stage peak-normalises each
    render close to 0 dBFS (see stages/voice.py's ``postprocess_voice``),
    which is correct for a standalone WAV but leaves a huge crest factor —
    a couple of transient sample peaks near 0 dBFS sit far above the rest
    of the speech's RMS level. Two-pass ``loudnorm`` in linear mode never
    exceeds the true-peak ceiling, so with an untamed ~0 dBFS peak it has
    to leave the *integrated* loudness well under the -14 LUFS target to
    avoid clipping. This was tuned empirically against real renders (see
    README's "Real end-to-end verification"): with no limiter, measured
    integrated loudness landed at -15.0 to -17 LUFS despite two-pass
    linear normalisation (1+ LU short of -14). A -6 dB ceiling closed most
    of that gap but left too little margin once AAC re-encoding's true-peak
    overshoot is accounted for (final encoded true peak measured up to
    -0.42 dBTP on some renders — above the -1 dBTP requirement even though
    the pre-encode PCM hit exactly -1.5 dBTP). -9 dB gives loudnorm enough
    headroom to reach -14 LUFS (measured -13.98 to -14.13 across two real
    renders) while ``compose.true_peak_dbtp``'s default of -2.5 dBTP
    (rather than -1.5) leaves margin for that codec overshoot, landing the
    final AAC file at -1.4 to -2.4 dBTP in practice — comfortably under
    the -1 dBTP requirement. The limiter runs with ``level=disabled`` so
    it only clamps the outlier peaks rather than also auto-normalising the
    whole signal upward.

    Used twice: once standalone (pass 1, to measure loudness with
    ``ffmpeg -af ... loudnorm=print_format=json -f null -``), and once as
    the audio half of the full compose filtergraph in pass 2 (see
    ``build_compose_filtergraph``'s ``loudnorm_filter`` param) — the two
    invocations must produce bit-identical audio so the pass-1 measurement
    is valid for what pass 2 actually encodes, which is why this is a
    single shared function rather than the mix logic being duplicated.
    """
    parts: list[str] = []
    if has_music:
        parts.append(f"[{music_input_idx}:a]volume={music_volume_db}dB[music_g]")
        if duck_under_voice:
            parts.append(
                f"[music_g][{voice_input_idx}:a]sidechaincompress="
                "threshold=0.05:ratio=8:attack=5:release=300[ducked]"
            )
            mix_inputs = f"[{voice_input_idx}:a][ducked]"
        else:
            mix_inputs = f"[{voice_input_idx}:a][music_g]"
        premix_label = "[premixed]" if pre_limiter_db is not None else "[premix]"
        parts.append(f"{mix_inputs}amix=inputs=2:duration=first:dropout_transition=2{premix_label}")
    else:
        premix_label = "[premixed]" if pre_limiter_db is not None else "[premix]"
        parts.append(f"[{voice_input_idx}:a]anull{premix_label}")

    if pre_limiter_db is not None:
        limit_linear = 10 ** (pre_limiter_db / 20)
        parts.append(
            f"[premixed]alimiter=limit={limit_linear:.6f}:attack=1:release=50:level=disabled[premix]"
        )
    return {"filter_complex": ";".join(parts), "audio_map": "[premix]"}


@dataclass
class LoudnormMeasurement:
    """Fields from ffmpeg's ``loudnorm=print_format=json`` pass-1 output,
    fed into pass 2's ``measured_*``/``offset`` args for a linear,
    accurate two-pass normalisation (see ``build_loudnorm_filter``)."""

    input_i: float
    input_tp: float
    input_lra: float
    input_thresh: float
    target_offset: float


LOUDNORM_JSON_KEYS = (
    "input_i",
    "input_tp",
    "input_lra",
    "input_thresh",
    "target_offset",
)


def parse_loudnorm_json(text: str) -> LoudnormMeasurement:
    """Extract and parse the JSON object ffmpeg's loudnorm filter prints to
    stderr with ``print_format=json`` (mixed in among other stderr log
    lines, so we locate the outermost ``{...}`` block rather than trying
    to parse the whole stream as JSON)."""
    match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if not match:
        # loudnorm's block can contain nested braces in newer ffmpeg
        # builds; fall back to the last balanced-looking block.
        matches = re.findall(r"\{.*?\}", text, re.DOTALL)
        if not matches:
            raise ValueError("no JSON object found in loudnorm output")
        match_text = matches[-1]
    else:
        match_text = match.group(0)
    data = json.loads(match_text)
    missing = [k for k in LOUDNORM_JSON_KEYS if k not in data]
    if missing:
        raise ValueError(f"loudnorm JSON missing expected keys: {missing}")
    return LoudnormMeasurement(
        input_i=float(data["input_i"]),
        input_tp=float(data["input_tp"]),
        input_lra=float(data["input_lra"]),
        input_thresh=float(data["input_thresh"]),
        target_offset=float(data["target_offset"]),
    )


def build_loudnorm_filter(
    loudness_lufs: float,
    true_peak: float = -1.5,
    lra: float = 11.0,
    measured: LoudnormMeasurement | None = None,
) -> str:
    """Build a ``loudnorm`` filter string. Single-pass (measured=None) is
    what ffmpeg's docs call "dynamic" mode — a quick one-shot estimate,
    typically within a couple of LU of the target. Two-pass (measured
    given) uses ``linear=true`` with the pass-1 measurements, which is
    accurate to a tenth of an LU or so, at the cost of running ffmpeg
    twice."""
    base = f"loudnorm=I={loudness_lufs}:TP={true_peak}:LRA={lra}"
    if measured is None:
        return base
    return (
        f"{base}:measured_I={measured.input_i}:measured_TP={measured.input_tp}:"
        f"measured_LRA={measured.input_lra}:measured_thresh={measured.input_thresh}:"
        f"offset={measured.target_offset}:linear=true"
    )


def build_compose_filtergraph(
    *,
    width: int,
    height: int,
    fps: int,
    layout: str,
    ass_path: Path,
    has_background_video: bool,
    has_music: bool,
    duck_under_voice: bool,
    loudness_lufs: float,
    music_volume_db: float,
    loudnorm_filter: str | None = None,
) -> dict:
    """Build the filtergraph pieces for the compose stage.

    Returns a dict with:
      - "filter_complex": the -filter_complex string
      - "video_map": label to map for video output
      - "audio_map": label to map for audio output

    Inputs are assumed in this order: 0=background, 1=face, 2=voice,
    3=music (only if has_music).

    ``loudnorm_filter``: a pre-built loudnorm filter fragment (see
    ``build_loudnorm_filter``) to apply to the mixed audio. Defaults to a
    single-pass ``loudnorm=I=...:TP=-1.5:LRA=11`` fragment built from
    ``loudness_lufs`` when not given, for callers/tests that don't need
    two-pass accuracy.
    """
    if layout not in LAYOUTS:
        raise ValueError(f"unknown layout {layout!r}, expected one of {LAYOUTS}")

    parts: list[str] = []

    # Background: scale+crop to fill WxH (covers both image and video sources).
    parts.append(
        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},fps={fps},setsar=1[bg]"
    )

    if layout == "full_face":
        face_h = height
        face_y = 0
    elif layout == "face_top":
        face_h = int(height * 0.62)
        face_y = 0
    else:  # face_bottom
        face_h = int(height * 0.62)
        face_y = height - face_h

    parts.append(
        f"[1:v]scale={width}:{face_h}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{face_h}:(ow-iw)/2:(oh-ih)/2:color=black@0,fps={fps},setsar=1[face]"
    )
    parts.append(f"[bg][face]overlay=x=(W-w)/2:y={face_y}:shortest=1[comp]")

    ass_arg = escape_filter_path(ass_path)
    parts.append(f"[comp]ass={ass_arg}[capped]")

    # Audio: voice is input 2, optional music is input 3.
    premix = build_audio_premix_filtergraph(
        has_music=has_music,
        duck_under_voice=duck_under_voice,
        music_volume_db=music_volume_db,
        voice_input_idx=2,
        music_input_idx=3,
    )
    parts.append(premix["filter_complex"])

    ln_filter = loudnorm_filter or build_loudnorm_filter(loudness_lufs)
    parts.append(f"{premix['audio_map']}{ln_filter}[aout]")

    filter_complex = ";".join(parts)
    return {
        "filter_complex": filter_complex,
        "video_map": "[capped]",
        "audio_map": "[aout]",
    }


def run_ffmpeg(args: list[str], log_path: Path | None = None) -> subprocess.CompletedProcess:
    """Run ffmpeg with the given args (excluding the executable), streaming
    output to log_path if given. Raises CalledProcessError on failure.
    """
    cmd = [ffmpeg_exe(), "-y", *args]
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("\n$ " + " ".join(cmd) + "\n")
            result = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, text=True)
    else:
        result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        stderr = getattr(result, "stderr", None) or "(see log file)"
        raise subprocess.CalledProcessError(result.returncode, cmd, output=stderr)
    return result
