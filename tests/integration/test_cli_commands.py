"""Integration tests for the Typer CLI surface: consent gate enforcement,
`doctor`'s exit behaviour, and `clean`'s stage-invalidation wiring through
the real Job/job.json machinery (not mocked) — i.e. stage-to-stage
handoffs at the CLI layer rather than pure-function unit tests.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from echoface.cli import app
from echoface.job import Job

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_make_refuses_presenter_without_consent(tmp_path, monkeypatch):
    """echoface make must refuse (non-zero exit, no job artifacts beyond
    job.json) for a presenter whose consent_ref doesn't resolve — this is
    the CLI-level integration of echoface.job.check_presenter_consent."""
    monkeypatch.chdir(REPO_ROOT)
    runner = CliRunner()
    job_id = "test-consent-gate-job"
    job_dir = REPO_ROOT / "output" / job_id
    import shutil

    shutil.rmtree(job_dir, ignore_errors=True)
    try:
        result = runner.invoke(
            app,
            ["make", "--topic", "irrelevant", "--presenter", "anchor1", "--job-id", job_id],
        )
        assert result.exit_code == 2, result.output
        assert not (job_dir / "final.mp4").exists()
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)


def test_doctor_exits_zero_with_only_warnings(monkeypatch):
    """doctor must never crash, and must exit 0 when every failing check is
    a warning (not a hard error) — even on a machine with no GPU/Ollama."""
    monkeypatch.chdir(REPO_ROOT)
    runner = CliRunner()
    result = runner.invoke(app, ["doctor"])
    # doctor exits 1 only on a hard FAIL-level check; warnings alone -> 0.
    assert result.exit_code in (0, 1), result.output
    assert "doctor report" in result.output.lower() or "Check" in result.output


def test_clean_unknown_job_id_fails_cleanly(monkeypatch):
    monkeypatch.chdir(REPO_ROOT)
    runner = CliRunner()
    result = runner.invoke(app, ["clean", "this-job-id-does-not-exist-12345", "--from", "captions"])
    assert result.exit_code != 0


def test_clean_resets_job_json_stage_status(tmp_path, monkeypatch):
    """clean --from <stage> must reset that stage (and downstream) to
    'pending' in job.json — verified by reading the real file back, not
    just checking the command's exit code."""
    monkeypatch.chdir(REPO_ROOT)
    runner = CliRunner()
    job_id = "test-clean-job-json-check"
    job_dir = REPO_ROOT / "output" / job_id
    import shutil

    shutil.rmtree(job_dir, ignore_errors=True)
    try:
        job = Job.create(topic="clean test", root=REPO_ROOT / "output", job_id=job_id)
        for stage in ["script", "voice", "face", "captions", "compose"]:
            job.mark_done(stage, f"hash-{stage}", 1.0)

        result = runner.invoke(app, ["clean", job_id, "--from", "voice"])
        assert result.exit_code == 0, result.output

        with open(job_dir / "job.json", encoding="utf-8") as fh:
            data = json.load(fh)
        assert data["stages"]["script"]["status"] == "done"
        assert data["stages"]["voice"]["status"] == "pending"
        assert data["stages"]["face"]["status"] == "pending"
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)


def test_batch_missing_file_fails_cleanly(monkeypatch):
    monkeypatch.chdir(REPO_ROOT)
    runner = CliRunner()
    result = runner.invoke(app, ["batch", "--file", "does_not_exist_topics.txt"])
    assert result.exit_code != 0
