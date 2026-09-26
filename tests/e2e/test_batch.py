"""Happy-path test for `echoface batch`: real batch loop, real
run_pipeline, real ffmpeg compose — with the script stage's Ollama HTTP
call mocked (so this doesn't need a live Ollama server) and dummy
voice/face/captions engines (so it doesn't need a GPU). This was a real
gap flagged in docs/project/improvements-and-known-issues.md: only
`batch`'s failure mode (missing topics file) had a test before this.
"""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from echoface.cli import app
from echoface.util.ffmpeg import ffmpeg_available

pytestmark = pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg/ffprobe not on PATH")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

FAKE_SCRIPT_JSON = json.dumps(
    {
        "title": "Batch Test Topic",
        "hook": "This is a fake hook for testing.",
        "lines": ["A fake supporting line here.", "Another fake line follows."],
        "cta": "Fake call to action.",
        "description": "A fake description for the batch test.",
        "tags": ["test", "batch"],
    }
)


@pytest.fixture
def cleanup_output_dirs():
    created: list[Path] = []
    yield created
    for d in created:
        shutil.rmtree(d, ignore_errors=True)


def test_batch_happy_path_renders_every_topic(tmp_path, cleanup_output_dirs, monkeypatch):
    monkeypatch.chdir(REPO_ROOT)
    topics_file = tmp_path / "topics.txt"
    suffix = uuid.uuid4().hex[:8]
    topics_file.write_text(f"first batch topic {suffix}\nsecond batch topic {suffix}\n", encoding="utf-8")

    # Snapshot existing job dirs so we can find the ones batch creates
    # (batch auto-generates timestamp+slug job IDs, not deterministic).
    output_root = REPO_ROOT / "output"
    before = set(output_root.iterdir()) if output_root.exists() else set()

    runner = CliRunner()
    with patch("echoface.stages.script.call_ollama", return_value=FAKE_SCRIPT_JSON):
        result = runner.invoke(
            app,
            [
                "batch",
                "--file",
                str(topics_file),
                "--presenter",
                "smoketest",
                "--config",
                "tests/fixtures/dummy_batch.yaml",
            ],
        )

    assert result.exit_code == 0, result.output
    assert "Job" not in result.output or "failed" not in result.output.lower()

    after = set(output_root.iterdir())
    new_dirs = sorted(after - before)
    cleanup_output_dirs.extend(new_dirs)

    assert len(new_dirs) == 2, f"expected 2 new job dirs, got {[d.name for d in new_dirs]}"
    for job_dir in new_dirs:
        assert (job_dir / "final.mp4").exists(), f"{job_dir} missing final.mp4"
        assert (job_dir / "metadata.json").exists()
        assert (job_dir / "script.json").exists()
        script = json.loads((job_dir / "script.json").read_text(encoding="utf-8"))
        assert script["title"] == "Batch Test Topic"


def test_batch_continues_past_a_single_job_failure(tmp_path, cleanup_output_dirs, monkeypatch):
    """One topic's script generation fails (simulated); batch must still
    process the remaining topics rather than aborting entirely."""
    monkeypatch.chdir(REPO_ROOT)
    topics_file = tmp_path / "topics.txt"
    suffix = uuid.uuid4().hex[:8]
    topics_file.write_text(f"will fail {suffix}\nwill succeed {suffix}\n", encoding="utf-8")

    output_root = REPO_ROOT / "output"
    before = set(output_root.iterdir()) if output_root.exists() else set()

    call_count = {"n": 0}

    def flaky_call_ollama(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("simulated Ollama failure for the first topic")
        return FAKE_SCRIPT_JSON

    runner = CliRunner()
    with patch("echoface.stages.script.call_ollama", side_effect=flaky_call_ollama):
        result = runner.invoke(
            app,
            [
                "batch",
                "--file",
                str(topics_file),
                "--presenter",
                "smoketest",
                "--config",
                "tests/fixtures/dummy_batch.yaml",
            ],
        )

    # batch itself must exit 0 (it catches per-job exceptions) even though
    # one job failed.
    assert result.exit_code == 0, result.output
    assert "failed" in result.output.lower()

    after = set(output_root.iterdir())
    new_dirs = sorted(after - before)
    cleanup_output_dirs.extend(new_dirs)

    # Both job dirs get created (Job.create happens before the failure),
    # but only the second should have a final.mp4.
    assert len(new_dirs) == 2
    finals = [d for d in new_dirs if (d / "final.mp4").exists()]
    assert len(finals) == 1
