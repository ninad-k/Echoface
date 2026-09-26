"""Integration test: config precedence (CLI flag > environment variable
(.env) > yaml file > pydantic default) — echoface.config.load_config's
full chain. See docs/architecture/adr/0008-config-precedence-cli-over-env.md
for why CLI beats env (changed from the original env>CLI order in v0.1.0).
"""

from __future__ import annotations

from echoface.config import load_config


def test_precedence_default_only(tmp_path, monkeypatch):
    monkeypatch.delenv("ECHOFACE_OLLAMA_HOST", raising=False)
    cfg = load_config(tmp_path / "does_not_exist.yaml")
    assert cfg.script.host == "http://localhost:11434"  # pydantic default


def test_precedence_yaml_overrides_default(tmp_path, monkeypatch):
    monkeypatch.delenv("ECHOFACE_OLLAMA_HOST", raising=False)
    yaml_path = tmp_path / "cfg.yaml"
    yaml_path.write_text("script:\n  host: http://yaml-host:11434\n", encoding="utf-8")
    cfg = load_config(yaml_path)
    assert cfg.script.host == "http://yaml-host:11434"


def test_precedence_env_var_beats_yaml(tmp_path, monkeypatch):
    yaml_path = tmp_path / "cfg.yaml"
    yaml_path.write_text("script:\n  host: http://yaml-host:11434\n", encoding="utf-8")
    monkeypatch.setenv("ECHOFACE_OLLAMA_HOST", "http://env-host:11434")
    cfg = load_config(yaml_path)
    assert cfg.script.host == "http://env-host:11434"
    monkeypatch.delenv("ECHOFACE_OLLAMA_HOST", raising=False)


def test_precedence_cli_override_beats_env_var(tmp_path, monkeypatch):
    """The key behaviour change in this version: an explicit CLI flag
    wins over a .env value, not the other way around."""
    yaml_path = tmp_path / "cfg.yaml"
    yaml_path.write_text("script:\n  host: http://yaml-host:11434\n", encoding="utf-8")
    monkeypatch.setenv("ECHOFACE_OLLAMA_HOST", "http://env-host:11434")
    cfg = load_config(yaml_path, overrides={"script": {"host": "http://cli-host:11434"}})
    assert cfg.script.host == "http://cli-host:11434"
    monkeypatch.delenv("ECHOFACE_OLLAMA_HOST", raising=False)


def test_precedence_cli_override_beats_yaml_with_no_env_set(tmp_path, monkeypatch):
    monkeypatch.delenv("ECHOFACE_OLLAMA_HOST", raising=False)
    yaml_path = tmp_path / "cfg.yaml"
    yaml_path.write_text("script:\n  host: http://yaml-host:11434\n", encoding="utf-8")
    cfg = load_config(yaml_path, overrides={"script": {"host": "http://cli-host:11434"}})
    assert cfg.script.host == "http://cli-host:11434"


def test_env_override_for_piper_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("ECHOFACE_PIPER_EXE", "C:/custom/piper.exe")
    monkeypatch.setenv("ECHOFACE_PIPER_MODEL", "C:/custom/voice.onnx")
    cfg = load_config(tmp_path / "missing.yaml")
    assert cfg.voice.piper_exe == "C:/custom/piper.exe"
    assert cfg.voice.piper_model == "C:/custom/voice.onnx"
    monkeypatch.delenv("ECHOFACE_PIPER_EXE", raising=False)
    monkeypatch.delenv("ECHOFACE_PIPER_MODEL", raising=False)


def test_env_override_overridden_by_cli_for_piper_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("ECHOFACE_PIPER_EXE", "C:/custom/piper.exe")
    cfg = load_config(tmp_path / "missing.yaml", overrides={"voice": {"piper_exe": "C:/cli/piper.exe"}})
    assert cfg.voice.piper_exe == "C:/cli/piper.exe"
    monkeypatch.delenv("ECHOFACE_PIPER_EXE", raising=False)
