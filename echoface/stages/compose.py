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
        out_path = self.job.path_for("final.mp4")

        # Pass 1: measure the mixed (voice + ducked music) audio's loudness
        # with ffmpeg's loudnorm filter in JSON-measurement mode. Pass 2
        # (the real encode below) then applies loudnorm in linear mode with
        # those measured values, which lands within a fraction of a LU of
        # the target instead of single-pass "dynamic" mode's few-LU slop.
        #
        # Even two-pass linear mode isn't a hard guarantee once AAC
        # re-encoding is in the loop (see ADR-0004/0009): AAC can overshoot
        # the pre-encode PCM's true peak by up to ~1 dB, and the achievable
        # integrated loudness depends on the source's own crest factor.
        # So after encoding, we MEASURE THE ACTUAL FINAL FILE and, if it's
        # outside spec (loudness_tolerance_lu / loudness_hard_tp_ceiling_dbtp),
        # correct the offset/TP-margin and re-encode once — up to
        # loudness_max_encode_attempts total attempts, never looping
        # forever on adversarial input.
        pre_encode_measurement = self._measure_loudness(voice_path, has_music, comp)
        offset_correction = 0.0
        tp_correction = 0.0
        final_measurement: ffm.LoudnormMeasurement | None = None

        for attempt in range(1, max(1, comp.loudness_max_encode_attempts) + 1):
            corrected = ffm.LoudnormMeasurement(
                input_i=pre_encode_measurement.input_i,
                input_tp=pre_encode_measurement.input_tp,
                input_lra=pre_encode_measurement.input_lra,
                input_thresh=pre_encode_measurement.input_thresh,
                target_offset=pre_encode_measurement.target_offset + offset_correction,
            )
            effective_tp_target = comp.true_peak_dbtp - tp_correction
            loudnorm_filter = ffm.build_loudnorm_filter(
                comp.loudness_lufs, true_peak=effective_tp_target, lra=comp.loudness_lra, measured=corrected
            )
            if self.logger:
                self.logger.info(
                    f"[compose] loudnorm attempt {attempt}: pre-encode target I={comp.loudness_lufs} "
                    f"TP<={effective_tp_target} (offset_correction={offset_correction:+.2f} LU, "
                    f"tp_correction={tp_correction:+.2f} dB)"
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
                pre_limiter_db=comp.pre_limiter_dbfs,
            )

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

            final_measurement = self._measure_final_file_loudness(out_path, comp)
            loudness_delta = comp.loudness_lufs - final_measurement.input_i
            tp_over = final_measurement.input_tp - comp.loudness_hard_tp_ceiling_dbtp
            in_spec = abs(loudness_delta) <= comp.loudness_tolerance_lu and tp_over <= 0
            if self.logger:
                self.logger.info(
                    f"[compose] final file measured: I={final_measurement.input_i:.2f} LUFS "
                    f"(target {comp.loudness_lufs}, delta {loudness_delta:+.2f} LU), "
                    f"TP={final_measurement.input_tp:.2f} dBTP "
                    f"(ceiling {comp.loudness_hard_tp_ceiling_dbtp}) -> "
                    f"{'OK' if in_spec else 'OUT OF SPEC'}"
                )
            if in_spec or attempt == comp.loudness_max_encode_attempts:
                if not in_spec and self.logger:
                    self.logger.warning(
                        f"[compose] loudness still out of spec after {attempt} attempt(s); "
                        "keeping the last encode. Consider tuning compose.pre_limiter_dbfs / "
                        "compose.true_peak_dbtp for this audio profile — see "
                        "docs/architecture/adr/0009-loudness-robustness.md"
                    )
                break
            # Correct and retry: nudge the gain offset to close the LUFS
            # gap, and tighten the pre-encode TP target by however much we
            # overshot the hard ceiling (plus a small safety margin) so
            # the next AAC encode has more headroom.
            offset_correction += loudness_delta
            if tp_over > 0:
                tp_correction += tp_over + 0.3

        assert final_measurement is not None
        self._write_metadata(duration, pre_encode_measurement, final_measurement)

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
            pre_limiter_db=comp.pre_limiter_dbfs,
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

    def _measure_final_file_loudness(self, final_path: Path, comp) -> ffm.LoudnormMeasurement:
        """Measure the ACTUAL encoded final.mp4's audio track (post-AAC),
        single-pass loudnorm in JSON-measurement mode — this is the number
        that matters for the ±0.5 LU / <=-1 dBTP spec, since it reflects
        whatever the codec did, not just what we asked ffmpeg's filter to
        produce pre-encode."""
        measure_filter = ffm.build_loudnorm_filter(
            comp.loudness_lufs, true_peak=comp.loudness_hard_tp_ceiling_dbtp, lra=comp.loudness_lra
        )
        cmd = [
            "-i",
            str(final_path),
            "-vn",
            "-af",
            f"{measure_filter}:print_format=json",
            "-f",
            "null",
            "-",
        ]
        result = ffm.run_ffmpeg(cmd)
        return ffm.parse_loudnorm_json(result.stderr or result.stdout or "")

    def _write_metadata(
        self,
        duration_s: float,
        pre_encode_measurement: ffm.LoudnormMeasurement,
        final_measurement: ffm.LoudnormMeasurement,
    ) -> None:
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
                "input_i": pre_encode_measurement.input_i,
                "input_tp": pre_encode_measurement.input_tp,
                "input_lra": pre_encode_measurement.input_lra,
            },
            "loudness_measured_final": {
                "input_i": final_measurement.input_i,
                "input_tp": final_measurement.input_tp,
                "input_lra": final_measurement.input_lra,
            },
            "disclosure_line": disclosure,
        }
        meta_path = self.job.path_for("metadata.json")
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(metadata, fh, indent=2)
