import pytest

from echoface.job import ConsentError, Job, check_presenter_consent, slugify


def test_slugify():
    assert slugify("3 Habits of Disciplined Traders!") == "3-habits-of-disciplined-traders"
    assert slugify("") == "job"


def test_job_create_and_load(tmp_path):
    job = Job.create(topic="Test Topic", root=tmp_path)
    assert job.job_dir.exists()
    assert job.json_path.exists()

    loaded = Job.load(job.job_id, root=tmp_path)
    assert loaded.topic == "Test Topic"
    assert loaded.job_id == job.job_id


def test_stage_skip_logic(tmp_path):
    job = Job.create(topic="skip test", root=tmp_path)
    out_file = job.path_for("script.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)

    # Not done yet: no file, no recorded hash.
    assert job.is_stage_done("script", "hash1", [out_file]) is False

    out_file.write_text("{}")
    job.mark_done("script", "hash1", 1.23)

    # Same hash + file exists -> should skip.
    assert job.is_stage_done("script", "hash1", [out_file]) is True

    # Different hash -> should NOT skip even though file exists.
    assert job.is_stage_done("script", "hash2", [out_file]) is False

    # Same hash but file deleted -> should NOT skip.
    out_file.unlink()
    assert job.is_stage_done("script", "hash1", [out_file]) is False


def test_clean_invalidates_downstream(tmp_path):
    job = Job.create(topic="clean test", root=tmp_path)
    for stage in ["script", "voice", "face", "captions", "compose"]:
        job.mark_done(stage, f"hash-{stage}", 1.0)

    cleaned = job.clean_from("face")
    assert cleaned == ["face", "captions", "compose"]

    assert job.stages["script"].status == "done"
    assert job.stages["voice"].status == "done"
    assert job.stages["face"].status == "pending"
    assert job.stages["captions"].status == "pending"
    assert job.stages["compose"].status == "pending"

    # Reloading from disk should reflect the reset.
    reloaded = Job.load(job.job_id, root=tmp_path)
    assert reloaded.stages["face"].status == "pending"
    assert reloaded.stages["script"].status == "done"


def test_create_with_existing_job_id_preserves_stage_state(tmp_path):
    """Regression test: `echoface make --job-id <existing>` must not wipe
    out prior stage progress — found via real end-to-end testing, where
    re-running `make` with the same --job-id silently redid a ~2 minute
    GPU face stage because Job.create() always wrote a blank job.json."""
    job = Job.create(topic="idempotent re-create", root=tmp_path, job_id="fixed-id")
    job.mark_done("script", "hash-script", 1.0)
    job.mark_done("voice", "hash-voice", 2.0)

    recreated = Job.create(topic="idempotent re-create", root=tmp_path, job_id="fixed-id")
    assert recreated.stages["script"].status == "done"
    assert recreated.stages["script"].config_hash == "hash-script"
    assert recreated.stages["voice"].status == "done"


def test_clean_unknown_stage_raises(tmp_path):
    job = Job.create(topic="x", root=tmp_path)
    with pytest.raises(ValueError):
        job.clean_from("not-a-stage")


def test_consent_check_missing_meta(tmp_path):
    presenters = tmp_path / "portraits"
    (presenters / "nobody").mkdir(parents=True)
    with pytest.raises(ConsentError):
        check_presenter_consent("nobody", presenters)


def test_consent_check_missing_consent_ref_file(tmp_path):
    presenters = tmp_path / "portraits"
    p_dir = presenters / "pres1"
    p_dir.mkdir(parents=True)
    (p_dir / "meta.yaml").write_text(
        "display_name: Pres1\nconsent_ref: consent/does_not_exist.pdf\n", encoding="utf-8"
    )
    with pytest.raises(ConsentError):
        check_presenter_consent("pres1", presenters)


def test_consent_check_passes_with_real_file(tmp_path):
    presenters = tmp_path / "portraits"
    p_dir = presenters / "pres1"
    p_dir.mkdir(parents=True)
    consent_file = tmp_path / "consent.pdf"
    consent_file.write_text("signed")
    (p_dir / "meta.yaml").write_text(
        f"display_name: Pres1\nconsent_ref: {consent_file.as_posix()}\n", encoding="utf-8"
    )
    meta = check_presenter_consent("pres1", presenters)
    assert meta["display_name"] == "Pres1"


def test_sample_anchor1_consent_is_deliberately_refused():
    """The shipped sample presenter references a consent file that does not
    exist on purpose (see consent/README.md) — verifies the gate actually
    fires against the real repo assets."""
    with pytest.raises(ConsentError):
        check_presenter_consent("anchor1")
