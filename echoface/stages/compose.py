"""Compose stage: face.mp4 + captions.ass + voice.wav (+ music) -> final.mp4
+ metadata.json, via a single ffmpeg filtergraph.
"""

from __future__ import annotations

import json
from pathlib import Path

from echoface.stages.base import Stage
from echoface.util import ffmpeg as ffm


def resolve_background(
    background: str | None, width: int, height: int, duration_s: float, color: str, out_dir: Path
) -> tuple[Path, bool]:
    """Return (path, is_video). If no background is configured (or the file
    is missing), generate a solid-colour video as a fallback so the
    filtergraph always has a valid input 0.
    """
    if background:
        path = Path(background)
        if path.exists():
            return path, path.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm")
    fallback = out_dir / "_background_fallback.mp4"
    ffm.run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s={width}x{height}:d={duration_s:.3f}:r=30",
            str(fallback),
        ]
    )
    return fallback, True


class ComposeStage(Stage):
    name = "compose"

    def inputs(self) -> list[Path]:
        return [
            self.job.path_for("face.mp4"),
            self.job.path_for("captions.ass"),
            self.job.path_for("voice.wav"),
            self.job.path_for("script.json"),
        ]

    def outputs(self) -> list[Path]:
        return [self.job.path_for("final.mp4"), self.job.path_for("metadata.json")]

    def run(self) -> None:
        comp = self.cfg.compose
        face_path = self.job.path_for("face.mp4")
        ass_path = self.job.path_for("captions.ass")
        voice_path = self.job.path_for("voice.wav")

        face_info = ffm.probe(face_path)
        duration = face_info.duration_s

        bg_path, _is_video = resolve_background(
            comp.background, comp.width, comp.height, duration, comp.background_color, self.job.job_dir
        )

        has_music = bool(comp.music and Path(comp.music).exists())

        # Pass 1: measure the mixed (voice + ducked music) audio's loudness
        # with ffmpeg's loudnorm filter in JSON-measurement mode. Pass 2
        # (the real encode below) then applies loudnorm in linear mode with
        # those measured values, which lands within a fraction of a LU of
        # the target instead of single-pass "dynamic" mode's few-LU slop.
        measurement = self._measure_loudness(voice_path, has_music, comp)
        loudnorm_filter = ffm.build_loudnorm_filter(
            comp.loudness_lufs, true_peak=comp.true_peak_dbtp, lra=comp.loudness_lra, measured=measurement
        )
        if self.logger:
            self.logger.info(
                f"[compose] loudnorm pass 1: measured I={measurement.input_i} LUFS, "
                f"TP={measurement.input_tp} dBTP, LRA={measurement.input_lra} LU"
            )

        graph = ffm.build_compose_filtergraph(
            width=comp.width,
            height=comp.height,
            fps=comp.fps,
            layout=comp.layout,
            ass_path=ass_path,
            has_background_video=True,
            has_music=has_music,
            duck_under_voice=comp.duck_under_voice,
            loudness_lufs=comp.loudness_lufs,
            music_volume_db=comp.music_volume_db,
            loudnorm_filter=loudnorm_filter,
        )

        out_path = self.job.path_for("final.mp4")

        cmd = ["-i", str(bg_path), "-i", str(face_path), "-i", str(voice_path)]
        if has_music:
            cmd += ["-stream_loop", "-1", "-i", str(comp.music)]
        cmd += [
            "-filter_complex",
            graph["filter_complex"],
            "-map",
            graph["video_map"],
            "-map",
            graph["audio_map"],
            "-c:v",
            "libx264",
            "-profile:v",
            "high",
            "-crf",
            str(comp.crf),
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(comp.fps),
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            "-shortest",
            str(out_path),
        ]
        ffm.run_ffmpeg(cmd, log_path=self.job.run_log_path)

        self._write_metadata(duration, measurement)

    def _measure_loudness(self, voice_path: Path, has_music: bool, comp) -> ffm.LoudnormMeasurement:
        """Pass 1 of the two-pass loudnorm: mix voice(+ducked music) with the
        exact same premix filtergraph the final encode uses (same input
        order: 0=voice, 1=music), run loudnorm in JSON-measurement mode,
        and parse the result. No file is written — ``-f null -`` discards
        the audio itself; only stderr's JSON block is used.
        """
        premix = ffm.build_audio_premix_filtergraph(
            has_music=has_music,
            duck_under_voice=comp.duck_under_voice,
            music_volume_db=comp.music_volume_db,
            voice_input_idx=0,
            music_input_idx=1,
        )
        measure_filter = ffm.build_loudnorm_filter(
            comp.loudness_lufs, true_peak=comp.true_peak_dbtp, lra=comp.loudness_lra
        )
        filter_complex = (
            f"{premix['filter_complex']};{premix['audio_map']}{measure_filter}:print_format=json[measured]"
        )

        cmd = ["-i", str(voice_path)]
        if has_music:
            cmd += ["-stream_loop", "-1", "-i", str(comp.music)]
        cmd += [
            "-filter_complex",
            filter_complex,
            "-map",
            "[measured]",
            "-f",
            "null",
            "-",
        ]
        result = ffm.run_ffmpeg(cmd)
        return ffm.parse_loudnorm_json(result.stderr or result.stdout or "")

    def _write_metadata(self, duration_s: float, measurement: ffm.LoudnormMeasurement) -> None:
        script_path = self.job.path_for("script.json")
        with open(script_path, encoding="utf-8") as fh:
            script = json.load(fh)

        disclosure = self.cfg.compose.disclosure_line
        description = script.get("description", "")
        if disclosure not in description:
            description = f"{description}\n\n{disclosure}" if description else disclosure

        metadata = {
            "title": script.get("title"),
            "description": description,
            "tags": script.get("tags", []),
            "duration_s": duration_s,
            "presenter": self.cfg.presenter,
            "layout": self.cfg.compose.layout,
            "resolution": f"{self.cfg.compose.width}x{self.cfg.compose.height}",
            "fps": self.cfg.compose.fps,
            "loudness_lufs": self.cfg.compose.loudness_lufs,
            "loudness_measured_pass1": {
                "input_i": measurement.input_i,
                "input_tp": measurement.input_tp,
                "input_lra": measurement.input_lra,
            },
            "disclosure_line": disclosure,
        }
        meta_path = self.job.path_for("metadata.json")
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(metadata, fh, indent=2)
