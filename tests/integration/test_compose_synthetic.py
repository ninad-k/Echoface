"""Integration test: the compose stage's real ffmpeg pipeline (background
resolution, filtergraph, two-pass loudnorm, ASS burn-in) driven directly
against synthetic media (ffmpeg testsrc video, a sine-wave voice track, a
tiny hand-written ASS file) — no other stage involved, so this isolates
compose's own stage-to-stage contract (it reads face.mp4/captions.ass/
voice.wav/script.json, writes final.mp4/metadata.json) from the rest of
the pipeline. Skipped automatically if ffmpeg/ffprobe aren't on PATH.
"""

from __future__ import annotations

import json

import pytest

from echoface.config import EchofaceConfig
from echoface.job import Job
from echoface.stages.compose import ComposeStage
from echoface.util.ffmpeg import ffmpeg_available, probe, run_ffmpeg

pytestmark = pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg/ffprobe not on PATH")

TINY_ASS = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Arial,80,&H00FFFFFF,&H000080FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,2,2,60,60,180,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:03.00,Caption,,0,0,0,,{\\k100}Hello {\\k100}world
"""


@pytest.fixture
def synthetic_job(tmp_path):
    job = Job.create(topic="synthetic compose test", root=tmp_path, job_id="synthetic-compose")

    face_path = job.path_for("face.mp4")
    run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=480x480:rate=25:duration=3",
            "-pix_fmt",
            "yuv420p",
            str(face_path),
        ]
    )

    voice_path = job.path_for("voice.wav")
    run_ffmpeg(
        ["-f", "lavfi", "-i", "sine=frequency=220:duration=3:sample_rate=22050", "-ac", "1", str(voice_path)]
    )

    ass_path = job.path_for("captions.ass")
    ass_path.write_text(TINY_ASS, encoding="utf-8")

    script_path = job.path_for("script.json")
    script_path.write_text(
        json.dumps(
            {
                "title": "Synthetic Test",
                "hook": "Hello world",
                "lines": [],
                "cta": "",
                "description": "A synthetic integration test render.",
                "tags": [],
            }
        ),
        encoding="utf-8",
    )
    return job


def test_compose_stage_produces_valid_final_mp4(synthetic_job, tmp_path):
    cfg = EchofaceConfig.model_validate(
        {
            "presenter": "synthetic",
            "compose": {
                "width": 1080,
                "height": 1920,
                "fps": 30,
                "layout": "face_top",
                "background": None,
                "music": None,
                "duck_under_voice": False,
                "loudness_lufs": -14,
                "crf": 22,
            },
        }
    )
    stage = ComposeStage(synthetic_job, cfg)
    stage.run()

    final_path = synthetic_job.path_for("final.mp4")
    metadata_path = synthetic_job.path_for("metadata.json")
    assert final_path.exists()
    assert metadata_path.exists()

    info = probe(final_path)
    assert info.width == 1080
    assert info.height == 1920
    assert info.has_audio
    assert info.has_video

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["title"] == "Synthetic Test"
    assert "Presenter is AI-generated." in metadata["description"]
    assert "loudness_measured_pass1" in metadata


def test_compose_stage_is_idempotent_via_is_done(synthetic_job):
    cfg = EchofaceConfig.model_validate({"presenter": "synthetic"})
    stage = ComposeStage(synthetic_job, cfg)
    assert stage.is_done() is False
    stage.execute()
    assert stage.is_done() is True
    # Re-running execute() should skip (0.0 duration) rather than re-encode.
    assert stage.execute() == 0.0
