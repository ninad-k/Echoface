from echoface.config import EchofaceConfig, config_hash, stage_hash


def test_load_defaults():
    cfg = EchofaceConfig()
    assert cfg.presenter == "anchor1"
    assert cfg.face.engine == "wav2lip"
    assert cfg.compose.layout == "face_top"


def test_config_hash_stable_and_order_independent():
    a = config_hash({"x": 1, "y": 2})
    b = config_hash({"y": 2, "x": 1})
    assert a == b


def test_config_hash_changes_with_value():
    a = config_hash({"x": 1})
    b = config_hash({"x": 2})
    assert a != b


def test_stage_hash_isolated_per_stage():
    cfg = EchofaceConfig()
    h_script = stage_hash(cfg, "script")
    h_voice = stage_hash(cfg, "voice")
    assert h_script != h_voice

    cfg2 = cfg.model_copy(deep=True)
    cfg2.voice.speed = 2.0
    # Changing voice config must not change the script hash.
    assert stage_hash(cfg, "script") == stage_hash(cfg2, "script")
    assert stage_hash(cfg, "voice") != stage_hash(cfg2, "voice")


def test_stage_hash_changes_with_global_fields():
    cfg = EchofaceConfig()
    cfg2 = cfg.model_copy(deep=True)
    cfg2.target_seconds = 60
    assert stage_hash(cfg, "voice") != stage_hash(cfg2, "voice")


def test_invalid_engine_rejected():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        EchofaceConfig.model_validate({"face": {"engine": "not-a-real-engine"}})
