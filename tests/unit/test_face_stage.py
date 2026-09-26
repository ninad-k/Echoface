import subprocess
from pathlib import Path

import pytest

from echoface.config import FaceConfig
from echoface.stages.face import (
    DummyFaceEngine,
    FaceBoxCache,
    FaceEngineError,
    SadTalkerEngine,
    Wav2LipEngine,
    build_engine,
    resolve_face_source,
    run_with_oom_retry,
)


def _cp(returncode, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=["fake"], returncode=returncode, stdout=stdout, stderr=stderr)


def test_run_with_oom_retry_succeeds_first_try():
    calls = []

    def run_fn(cmd, **kwargs):
        calls.append(cmd)
        return _cp(0, stdout="ok")

    result, batch, device = run_with_oom_retry(
        lambda b, d: ["cmd", f"--batch={b}", f"--device={d}"],
        initial_batch_size=32,
        device="cuda",
        run_fn=run_fn,
    )
    assert batch == 32
    assert device == "cuda"
    assert len(calls) == 1


def test_run_with_oom_retry_halves_batch_on_oom_then_succeeds():
    attempts = []

    def run_fn(cmd, **kwargs):
        batch = int([c for c in cmd if c.startswith("--batch=")][0].split("=")[1])
        attempts.append(batch)
        if batch > 8:
            return _cp(1, stderr="RuntimeError: CUDA out of memory.")
        return _cp(0)

    result, batch, device = run_with_oom_retry(
        lambda b, d: ["cmd", f"--batch={b}", f"--device={d}"],
        initial_batch_size=32,
        device="cuda",
        min_batch_size=4,
        run_fn=run_fn,
    )
    assert batch == 8
    assert device == "cuda"
    assert attempts == [32, 16, 8]


def test_run_with_oom_retry_falls_back_to_cpu():
    devices_tried = []

    def run_fn(cmd, **kwargs):
        device = [c for c in cmd if c.startswith("--device=")][0].split("=")[1]
        devices_tried.append(device)
        if device == "cuda":
            return _cp(1, stderr="CUDA out of memory")
        return _cp(0)

    result, batch, device = run_with_oom_retry(
        lambda b, d: ["cmd", f"--batch={b}", f"--device={d}"],
        initial_batch_size=4,
        device="cuda",
        min_batch_size=4,
        run_fn=run_fn,
    )
    assert device == "cpu"
    assert devices_tried[-1] == "cpu"


def test_run_with_oom_retry_raises_on_non_oom_failure():
    def run_fn(cmd, **kwargs):
        return _cp(1, stderr="FileNotFoundError: checkpoint missing")

    with pytest.raises(FaceEngineError):
        run_with_oom_retry(
            lambda b, d: ["cmd"],
            initial_batch_size=32,
            device="cuda",
            run_fn=run_fn,
        )


def test_run_with_oom_retry_raises_when_cpu_also_fails():
    def run_fn(cmd, **kwargs):
        return _cp(1, stderr="CUDA out of memory")

    with pytest.raises(FaceEngineError):
        run_with_oom_retry(
            lambda b, d: ["cmd", f"--batch={b}"],
            initial_batch_size=4,
            device="cuda",
            min_batch_size=4,
            run_fn=run_fn,
        )


def test_sadtalker_engine_passes_enhancer_flag_when_restore_gfpgan(tmp_path, monkeypatch):
    """SadTalker applies GFPGAN inline via its own runner flag rather than
    a separate post-process pass (see FaceStage.run's restore-skip logic
    for the wav2lip-only _apply_restore call) — verify the command is
    actually built with --enhancer gfpgan when configured."""
    captured_cmds = []

    def fake_run_with_oom_retry(build_cmd, **kwargs):
        cmd = build_cmd(kwargs["initial_batch_size"], kwargs["device"])
        captured_cmds.append(cmd)
        return None, kwargs["initial_batch_size"], kwargs["device"]

    monkeypatch.setattr("echoface.stages.face.run_with_oom_retry", fake_run_with_oom_retry)

    engine = SadTalkerEngine()
    cfg = FaceConfig(restore="gfpgan", device="cpu")
    engine.render(
        face_source=tmp_path / "portrait.png",
        audio_path=tmp_path / "voice_16k.wav",
        out_path=tmp_path / "face.mp4",
        cfg=cfg,
    )
    assert len(captured_cmds) == 1
    assert "--enhancer" in captured_cmds[0]
    assert "gfpgan" in captured_cmds[0]


def test_sadtalker_engine_no_enhancer_flag_when_restore_none(tmp_path, monkeypatch):
    captured_cmds = []

    def fake_run_with_oom_retry(build_cmd, **kwargs):
        captured_cmds.append(build_cmd(kwargs["initial_batch_size"], kwargs["device"]))
        return None, kwargs["initial_batch_size"], kwargs["device"]

    monkeypatch.setattr("echoface.stages.face.run_with_oom_retry", fake_run_with_oom_retry)

    engine = SadTalkerEngine()
    cfg = FaceConfig(restore="none", device="cpu")
    engine.render(
        face_source=tmp_path / "portrait.png",
        audio_path=tmp_path / "voice_16k.wav",
        out_path=tmp_path / "face.mp4",
        cfg=cfg,
    )
    assert "--enhancer" not in captured_cmds[0]


def test_face_box_cache_roundtrip(tmp_path):
    video = tmp_path / "idle.mp4"
    video.write_bytes(b"fake video bytes")

    cache = FaceBoxCache(tmp_path)
    assert cache.get(video) is None

    cache.set(video, {"box": [1, 2, 3, 4]})
    cached = cache.get(video)
    assert cached == {"box": [1, 2, 3, 4]}

    # A different file (different key) should miss.
    other = tmp_path / "other.mp4"
    other.write_bytes(b"different bytes")
    assert cache.get(other) is None


def test_build_engine_returns_correct_class():
    assert isinstance(build_engine(FaceConfig(engine="wav2lip")), Wav2LipEngine)
    assert isinstance(build_engine(FaceConfig(engine="sadtalker")), SadTalkerEngine)
    assert isinstance(build_engine(FaceConfig(engine="dummy")), DummyFaceEngine)


def test_resolve_face_source_prefers_idle_video(tmp_path):
    (tmp_path / "idle.mp4").write_bytes(b"fake")
    (tmp_path / "portrait.png").write_bytes(b"fake")
    assert resolve_face_source(tmp_path, "idle") == tmp_path / "idle.mp4"


def test_resolve_face_source_falls_back_to_photo_when_no_idle(tmp_path):
    (tmp_path / "portrait.jpg").write_bytes(b"fake")
    assert resolve_face_source(tmp_path, "idle") == tmp_path / "portrait.jpg"


def test_resolve_face_source_photo_explicit(tmp_path):
    (tmp_path / "portrait.jpeg").write_bytes(b"fake")
    assert resolve_face_source(tmp_path, "photo") == tmp_path / "portrait.jpeg"


def test_resolve_face_source_raises_when_nothing_found(tmp_path):
    with pytest.raises(FaceEngineError):
        resolve_face_source(tmp_path, "idle")


def test_apply_restore_codeformer_builds_correct_command(tmp_path, monkeypatch):
    """FaceStage._apply_restore must invoke scripts/codeformer_runner.py
    (not gfpgan_runner.py) when method='codeformer', with --region passed
    through from face.restore_region."""
    from echoface.job import Job
    from echoface.stages.face import FaceStage

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        # Simulate the runner having written the output file.
        out_idx = cmd.index("--outfile") + 1
        Path(cmd[out_idx]).write_bytes(b"fake restored video")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("echoface.stages.face.subprocess.run", fake_run)

    job = Job.create(topic="restore test", root=tmp_path, job_id="restore-test")
    cfg = FaceConfig(restore="codeformer", restore_region="mouth", device="cpu")
    from echoface.config import EchofaceConfig

    full_cfg = EchofaceConfig(face=cfg)
    stage = FaceStage(job, full_cfg)

    video_path = job.path_for("face.mp4")
    video_path.write_bytes(b"original video")
    stage._apply_restore(video_path, "codeformer")

    cmd = captured["cmd"]
    assert "scripts/codeformer_runner.py" in cmd
    assert "gfpgan_runner.py" not in " ".join(cmd)
    assert "--region" in cmd
    assert cmd[cmd.index("--region") + 1] == "mouth"
    assert video_path.read_bytes() == b"fake restored video"


def test_apply_restore_gfpgan_builds_correct_command(tmp_path, monkeypatch):
    from echoface.job import Job
    from echoface.stages.face import FaceStage

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        out_idx = cmd.index("--outfile") + 1
        Path(cmd[out_idx]).write_bytes(b"fake restored video")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("echoface.stages.face.subprocess.run", fake_run)

    job = Job.create(topic="restore test 2", root=tmp_path, job_id="restore-test-2")
    from echoface.config import EchofaceConfig

    full_cfg = EchofaceConfig(face=FaceConfig(restore="gfpgan", restore_region="face", device="cpu"))
    stage = FaceStage(job, full_cfg)
    video_path = job.path_for("face.mp4")
    video_path.write_bytes(b"original video")
    stage._apply_restore(video_path, "gfpgan")

    cmd = captured["cmd"]
    assert "scripts/gfpgan_runner.py" in cmd
    assert cmd[cmd.index("--region") + 1] == "face"
