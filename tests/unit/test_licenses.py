"""Unit tests for echoface.licenses: the machine-readable model/licence
table loader and config-matching logic that drives doctor's monetisation
warnings (v0.2.0 overhaul — was a single hardcoded Wav2Lip check)."""

from __future__ import annotations

from pathlib import Path

from echoface.licenses import (
    ModelLicense,
    active_models_for_config,
    load_licenses,
    non_commercial_active_models,
)

SAMPLE_YAML = """
models:
  - id: model_a
    name: "Model A"
    stage: face
    match: { face.engine: wav2lip }
    licence: "Non-commercial"
    commercial: false
    source: "https://example.com/a"
  - id: model_b
    name: "Model B"
    stage: voice
    match: { voice.engine: piper }
    licence: "MIT"
    commercial: true
    source: "https://example.com/b"
  - id: model_c
    name: "Model C"
    stage: face
    match: { face.restore: gfpgan }
    licence: "Unclear"
    commercial: check
    source: "https://example.com/c"
"""


def test_load_licenses_missing_file_returns_empty(tmp_path):
    assert load_licenses(tmp_path / "nope.yaml") == []


def test_load_licenses_malformed_yaml_returns_empty(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("not: valid: yaml: [", encoding="utf-8")
    assert load_licenses(p) == []


def test_load_licenses_parses_entries(tmp_path):
    p = tmp_path / "licenses.yaml"
    p.write_text(SAMPLE_YAML, encoding="utf-8")
    entries = load_licenses(p)
    assert len(entries) == 3
    assert entries[0].id == "model_a"
    assert entries[0].commercial is False
    assert entries[1].commercial is True
    assert entries[2].commercial == "check"


def test_model_license_status_label():
    assert ModelLicense("x", "X", "face", "MIT", True).status_label == "commercial-ok"
    assert ModelLicense("x", "X", "face", "NC", False).status_label == "non-commercial"
    assert ModelLicense("x", "X", "face", "?", "check").status_label == "unverified (check manually)"


def test_active_models_for_config_matches_correct_engine(tmp_path):
    p = tmp_path / "licenses.yaml"
    p.write_text(SAMPLE_YAML, encoding="utf-8")
    entries = load_licenses(p)

    cfg_wav2lip = {"face": {"engine": "wav2lip", "restore": "none"}, "voice": {"engine": "xtts"}}
    active = active_models_for_config(cfg_wav2lip, entries)
    assert {m.id for m in active} == {"model_a"}

    cfg_piper_gfpgan = {"face": {"engine": "sadtalker", "restore": "gfpgan"}, "voice": {"engine": "piper"}}
    active2 = active_models_for_config(cfg_piper_gfpgan, entries)
    assert {m.id for m in active2} == {"model_b", "model_c"}


def test_non_commercial_active_models_excludes_commercial_true(tmp_path):
    p = tmp_path / "licenses.yaml"
    p.write_text(SAMPLE_YAML, encoding="utf-8")
    entries = load_licenses(p)
    cfg = {"face": {"engine": "wav2lip", "restore": "gfpgan"}, "voice": {"engine": "piper"}}
    flagged = non_commercial_active_models(cfg, entries)
    assert {m.id for m in flagged} == {"model_a", "model_c"}  # model_b is commercial: true


def test_real_licenses_yaml_loads_and_flags_default_config():
    """Smoke test against the real models/licenses.yaml shipped in the
    repo, using the default EchofaceConfig (face.engine=wav2lip,
    face.restore=gfpgan) — should flag at least the Wav2Lip entry."""
    from echoface.config import EchofaceConfig

    entries = load_licenses(Path("models/licenses.yaml"))
    assert len(entries) > 0
    cfg = EchofaceConfig()
    flagged = non_commercial_active_models(cfg.model_dump(), entries)
    flagged_ids = {m.id for m in flagged}
    assert "wav2lip_gan" in flagged_ids
