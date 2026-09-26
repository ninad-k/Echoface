"""Unit tests for echoface.prune: duration parsing and the pure
candidate-finding logic (dry by construction — find_prune_candidates
never touches the filesystem beyond reading)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from echoface.prune import (
    apply_prune,
    find_prune_candidates,
    format_size,
    parse_duration,
)


def test_parse_duration_days():
    assert parse_duration("30d") == timedelta(days=30)


def test_parse_duration_hours():
    assert parse_duration("12h") == timedelta(hours=12)


def test_parse_duration_minutes():
    assert parse_duration("90m") == timedelta(minutes=90)


def test_parse_duration_case_insensitive():
    assert parse_duration("7D") == timedelta(days=7)


def test_parse_duration_rejects_garbage():
    with pytest.raises(ValueError):
        parse_duration("banana")
    with pytest.raises(ValueError):
        parse_duration("30")
    with pytest.raises(ValueError):
        parse_duration("30x")


def _make_job(root, job_id, age_days, with_final=True):
    job_dir = root / job_id
    job_dir.mkdir(parents=True)
    created_at = (datetime.now(UTC) - timedelta(days=age_days)).isoformat()
    (job_dir / "job.json").write_text(
        json.dumps({"job_id": job_id, "created_at": created_at}), encoding="utf-8"
    )
    (job_dir / "voice.wav").write_bytes(b"x" * 100)
    (job_dir / "face.mp4").write_bytes(b"x" * 200)
    if with_final:
        (job_dir / "final.mp4").write_bytes(b"x" * 500)
        (job_dir / "metadata.json").write_text("{}", encoding="utf-8")
    return job_dir


def test_find_prune_candidates_respects_age_threshold(tmp_path):
    _make_job(tmp_path, "old-job", age_days=40)
    _make_job(tmp_path, "new-job", age_days=1)
    candidates = find_prune_candidates(tmp_path, timedelta(days=30), keep_final=True)
    assert [c.job_id for c in candidates] == ["old-job"]


def test_find_prune_candidates_keep_final_excludes_final_files(tmp_path):
    _make_job(tmp_path, "old-job", age_days=40)
    candidates = find_prune_candidates(tmp_path, timedelta(days=30), keep_final=True)
    files = {f.name for f in candidates[0].files_to_remove}
    assert "final.mp4" not in files
    assert "metadata.json" not in files
    assert "voice.wav" in files
    assert "face.mp4" in files


def test_find_prune_candidates_no_keep_final_includes_everything(tmp_path):
    _make_job(tmp_path, "old-job", age_days=40)
    candidates = find_prune_candidates(tmp_path, timedelta(days=30), keep_final=False)
    files = {f.name for f in candidates[0].files_to_remove}
    assert "final.mp4" in files
    assert "metadata.json" in files


def test_find_prune_candidates_empty_on_missing_root(tmp_path):
    assert find_prune_candidates(tmp_path / "nope", timedelta(days=30), keep_final=True) == []


def test_apply_prune_keep_final_leaves_final_files_on_disk(tmp_path):
    job_dir = _make_job(tmp_path, "old-job", age_days=40)
    candidates = find_prune_candidates(tmp_path, timedelta(days=30), keep_final=True)
    freed = apply_prune(candidates)
    assert freed == 300  # voice.wav (100) + face.mp4 (200); job.json/final.mp4/metadata.json kept
    assert (job_dir / "final.mp4").exists()
    assert (job_dir / "metadata.json").exists()
    assert (job_dir / "job.json").exists()
    assert not (job_dir / "voice.wav").exists()
    assert not (job_dir / "face.mp4").exists()


def test_apply_prune_no_keep_final_removes_whole_job_dir(tmp_path):
    job_dir = _make_job(tmp_path, "old-job", age_days=40)
    candidates = find_prune_candidates(tmp_path, timedelta(days=30), keep_final=False)
    apply_prune(candidates)
    assert not job_dir.exists()


def test_apply_prune_does_not_touch_jobs_not_in_candidates(tmp_path):
    kept_dir = _make_job(tmp_path, "new-job", age_days=1)
    _make_job(tmp_path, "old-job", age_days=40)
    candidates = find_prune_candidates(tmp_path, timedelta(days=30), keep_final=False)
    apply_prune(candidates)
    assert kept_dir.exists()
    assert (kept_dir / "voice.wav").exists()


def test_format_size_units():
    assert format_size(500) == "500.0 B"
    assert format_size(2048) == "2.0 KB"
    assert format_size(5 * 1024 * 1024) == "5.0 MB"
