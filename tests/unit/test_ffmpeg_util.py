from pathlib import Path, PureWindowsPath

import pytest

from echoface.util.ffmpeg import (
    LoudnormMeasurement,
    build_audio_premix_filtergraph,
    build_chunk_plan,
    build_compose_filtergraph,
    build_loudnorm_filter,
    build_ping_pong_plan,
    escape_filter_path,
    parse_loudnorm_json,
)


def test_escape_filter_path_windows_drive_letter():
    p = PureWindowsPath(r"C:\echoface\output\job1\captions.ass")
    escaped = escape_filter_path(Path(str(p)))
    # Colon after drive letter must be escaped for the ffmpeg filter parser.
    assert "C\\:" in escaped
    # Backslashes normalised to forward slashes.
    assert "\\\\" not in escaped.replace("\\:", "")
    assert escaped.startswith("'") and escaped.endswith("'")


def test_build_ping_pong_plan_no_loop_needed():
    plan = build_ping_pong_plan(clip_duration_s=30, target_duration_s=20)
    assert plan == []


def test_build_ping_pong_plan_covers_target():
    plan = build_ping_pong_plan(clip_duration_s=5, target_duration_s=17)
    total = sum(d for _dir, d in plan)
    assert total >= 17
    directions = [d for d, _dur in plan]
    assert directions[0] == "forward"
    assert directions[1] == "reverse"
    # alternates
    for i in range(len(directions) - 1):
        assert directions[i] != directions[i + 1]


def test_build_ping_pong_plan_rejects_zero_duration():
    with pytest.raises(ValueError):
        build_ping_pong_plan(clip_duration_s=0, target_duration_s=10)


def test_build_chunk_plan_single_chunk_when_short():
    chunks = build_chunk_plan(30, chunk_seconds=40)
    assert chunks == [(0.0, 30)]


def test_build_chunk_plan_splits_long_audio():
    chunks = build_chunk_plan(90, chunk_seconds=40)
    assert len(chunks) == 3
    total = sum(d for _s, d in chunks)
    assert abs(total - 90) < 1e-6
    # starts are monotonic and contiguous
    starts = [s for s, _d in chunks]
    assert starts == sorted(starts)


def test_build_compose_filtergraph_layouts():
    for layout in ("face_top", "full_face", "face_bottom"):
        graph = build_compose_filtergraph(
            width=1080,
            height=1920,
            fps=30,
            layout=layout,
            ass_path=Path("output/job1/captions.ass"),
            has_background_video=True,
            has_music=False,
            duck_under_voice=True,
            loudness_lufs=-14,
            music_volume_db=-20,
        )
        assert graph["video_map"] == "[capped]"
        assert graph["audio_map"] == "[aout]"
        assert "ass=" in graph["filter_complex"]
        assert "overlay=" in graph["filter_complex"]
        assert "loudnorm=" in graph["filter_complex"]


def test_build_compose_filtergraph_with_music_ducking():
    graph = build_compose_filtergraph(
        width=1080,
        height=1920,
        fps=30,
        layout="face_top",
        ass_path=Path("captions.ass"),
        has_background_video=True,
        has_music=True,
        duck_under_voice=True,
        loudness_lufs=-14,
        music_volume_db=-20,
    )
    assert "sidechaincompress" in graph["filter_complex"]
    assert "amix=" in graph["filter_complex"]


def test_build_compose_filtergraph_music_no_ducking():
    graph = build_compose_filtergraph(
        width=1080,
        height=1920,
        fps=30,
        layout="face_top",
        ass_path=Path("captions.ass"),
        has_background_video=True,
        has_music=True,
        duck_under_voice=False,
        loudness_lufs=-14,
        music_volume_db=-20,
    )
    assert "sidechaincompress" not in graph["filter_complex"]
    assert "amix=" in graph["filter_complex"]


SAMPLE_LOUDNORM_STDERR = """
[Parsed_loudnorm_0 @ 0x0000020a1234abcd] Time delta [4.8194] is above what is allowed!
[Parsed_loudnorm_0 @ 0x0000020a1234abcd]
{
	"input_i" : "-23.71",
	"input_tp" : "-6.11",
	"input_lra" : "18.86",
	"input_thresh" : "-34.02",
	"output_i" : "-14.02",
	"output_tp" : "-1.55",
	"output_lra" : "9.00",
	"output_thresh" : "-24.15",
	"normalization_type" : "dynamic",
	"target_offset" : "0.02"
}
size=       0kB time=00:00:22.24 bitrate=   0.0kbits/s speed= 219x
"""


def test_parse_loudnorm_json_extracts_measured_fields():
    m = parse_loudnorm_json(SAMPLE_LOUDNORM_STDERR)
    assert isinstance(m, LoudnormMeasurement)
    assert m.input_i == pytest.approx(-23.71)
    assert m.input_tp == pytest.approx(-6.11)
    assert m.input_lra == pytest.approx(18.86)
    assert m.input_thresh == pytest.approx(-34.02)
    assert m.target_offset == pytest.approx(0.02)


def test_parse_loudnorm_json_no_json_raises():
    with pytest.raises(ValueError):
        parse_loudnorm_json("no json here, ffmpeg exploded")


def test_parse_loudnorm_json_missing_keys_raises():
    with pytest.raises(ValueError):
        parse_loudnorm_json('{"input_i": "-20.0"}')


def test_build_loudnorm_filter_single_pass_has_no_measured_fields():
    f = build_loudnorm_filter(-14.0, true_peak=-1.5, lra=11.0)
    assert f == "loudnorm=I=-14.0:TP=-1.5:LRA=11.0"
    assert "measured_I" not in f
    assert "linear=true" not in f


def test_build_loudnorm_filter_two_pass_includes_measured_and_linear():
    measured = LoudnormMeasurement(
        input_i=-23.71,
        input_tp=-6.11,
        input_lra=18.86,
        input_thresh=-34.02,
        target_offset=0.02,
    )
    f = build_loudnorm_filter(-14.0, true_peak=-1.5, lra=11.0, measured=measured)
    assert "loudnorm=I=-14.0:TP=-1.5:LRA=11.0" in f
    assert "measured_I=-23.71" in f
    assert "measured_TP=-6.11" in f
    assert "measured_LRA=18.86" in f
    assert "measured_thresh=-34.02" in f
    assert "offset=0.02" in f
    assert "linear=true" in f


def test_build_audio_premix_filtergraph_no_music():
    graph = build_audio_premix_filtergraph(has_music=False, duck_under_voice=True, music_volume_db=-20)
    assert graph["audio_map"] == "[premix]"
    assert "[0:a]" in graph["filter_complex"]
    assert "sidechaincompress" not in graph["filter_complex"]


def test_build_audio_premix_filtergraph_with_ducking():
    graph = build_audio_premix_filtergraph(has_music=True, duck_under_voice=True, music_volume_db=-20)
    assert "sidechaincompress" in graph["filter_complex"]
    assert "amix=inputs=2" in graph["filter_complex"]
    assert graph["filter_complex"].endswith("[premix]")


def test_build_audio_premix_filtergraph_custom_input_indices():
    graph = build_audio_premix_filtergraph(
        has_music=True,
        duck_under_voice=False,
        music_volume_db=-20,
        voice_input_idx=2,
        music_input_idx=3,
    )
    assert "[2:a]" in graph["filter_complex"]
    assert "[3:a]" in graph["filter_complex"]


def test_build_compose_filtergraph_uses_two_pass_loudnorm_filter_when_given():
    two_pass = build_loudnorm_filter(-14.0, measured=LoudnormMeasurement(-23.71, -6.11, 18.86, -34.02, 0.02))
    graph = build_compose_filtergraph(
        width=1080,
        height=1920,
        fps=30,
        layout="face_top",
        ass_path=Path("captions.ass"),
        has_background_video=True,
        has_music=False,
        duck_under_voice=True,
        loudness_lufs=-14,
        music_volume_db=-20,
        loudnorm_filter=two_pass,
    )
    assert "measured_I=-23.71" in graph["filter_complex"]
    assert "linear=true" in graph["filter_complex"]


def test_build_compose_filtergraph_rejects_unknown_layout():
    with pytest.raises(ValueError):
        build_compose_filtergraph(
            width=1080,
            height=1920,
            fps=30,
            layout="nope",
            ass_path=Path("captions.ass"),
            has_background_video=True,
            has_music=False,
            duck_under_voice=True,
            loudness_lufs=-14,
            music_volume_db=-20,
        )
