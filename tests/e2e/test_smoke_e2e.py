"""End-to-end smoke test: --script-file + dummy voice/face/captions engines
through the real ffmpeg compose stage. Skipped automatically if ffmpeg /
ffprobe aren't on PATH. Runs from the repo root (pytest's default cwd),
using tests/fixtures/dummy.yaml and the 'smoketest' presenter under
assets/portraits/.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from echoface.cli import app
from echoface.util.ffmpeg import ffmpeg_available, probe

pytestmark = pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg/ffprobe not on PATH")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def cleanup_jobs():
    created = []
    yield created
    for job_dir in created:
        shutil.rmtree(job_dir, ignore_errors=True)


def test_make_end_to_end_with_dummy_engines(cleanup_jobs):
    runner = CliRunner()
    job_id = "test-smoke-e2e-job"
    job_dir = REPO_ROOT / "output" / job_id
    shutil.rmtree(job_dir, ignore_errors=True)
    cleanup_jobs.append(job_dir)

    result = runner.invoke(
        app,
        [
            "make",
            "--script-file",
            "tests/fixtures/sample_script.txt",
            "--config",
            "tests/fixtures/dummy.yaml",
            "--presenter",
            "smoketest",
            "--job-id",
            job_id,
        ],
    )
    assert result.exit_code == 0, result.output

    final_path = job_dir / "final.mp4"
    metadata_path = job_dir / "metadata.json"
    assert final_path.exists(), result.output
    assert metadata_path.exists()

    info = probe(final_path)
    assert info.width == 1080
    assert info.height == 1920
    assert info.has_audio
    assert info.has_video
    assert info.fps is not None and round(info.fps) == 30

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert "Presenter is AI-generated." in metadata["description"]

    # Re-running should skip every stage (idempotent) and still succeed.
    result2 = runner.invoke(
        app,
        [
            "make",
            "--script-file",
            "tests/fixtures/sample_script.txt",
            "--config",
            "tests/fixtures/dummy.yaml",
            "--presenter",
            "smoketest",
            "--job-id",
            job_id,
        ],
    )
    assert result2.exit_code == 0, result2.output


def test_clean_then_resume(cleanup_jobs):
    runner = CliRunner()
    job_id = "test-smoke-clean-job"
    job_dir = REPO_ROOT / "output" / job_id
    shutil.rmtree(job_dir, ignore_errors=True)
    cleanup_jobs.append(job_dir)

    result = runner.invoke(
        app,
        [
            "make",
            "--script-file",
            "tests/fixtures/sample_script.txt",
            "--config",
            "tests/fixtures/dummy.yaml",
            "--presenter",
            "smoketest",
            "--job-id",
            job_id,
        ],
    )
    assert result.exit_code == 0, result.output

    clean_result = runner.invoke(app, ["clean", job_id, "--from", "captions"])
    assert clean_result.exit_code == 0, clean_result.output
    assert not (job_dir / "final.mp4").exists()

    resume_result = runner.invoke(app, ["resume", job_id, "--config", "tests/fixtures/dummy.yaml"])
    assert resume_result.exit_code == 0, resume_result.output
    assert (job_dir / "final.mp4").exists()
