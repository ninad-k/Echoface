"""Unit tests for echoface.doctor's pure-logic pieces: the run_doctor
report never crashes, and the configurable network-probe timeout."""

from __future__ import annotations

from echoface.config import EchofaceConfig
from echoface.doctor import Check, _doctor_timeout, run_doctor


def test_doctor_timeout_default():
    assert _doctor_timeout() == 3.0


def test_doctor_timeout_env_override(monkeypatch):
    monkeypatch.setenv("ECHOFACE_DOCTOR_TIMEOUT_S", "10")
    assert _doctor_timeout() == 10.0
    monkeypatch.delenv("ECHOFACE_DOCTOR_TIMEOUT_S", raising=False)


def test_doctor_timeout_ignores_garbage_env_value(monkeypatch):
    monkeypatch.setenv("ECHOFACE_DOCTOR_TIMEOUT_S", "not-a-number")
    assert _doctor_timeout() == 3.0
    monkeypatch.delenv("ECHOFACE_DOCTOR_TIMEOUT_S", raising=False)


def test_run_doctor_never_crashes_and_returns_checks(tmp_path, monkeypatch):
    """The whole point of doctor: it must produce a report (list[Check])
    even when nothing (GPU, Ollama, model files) is present."""
    monkeypatch.chdir(tmp_path)
    cfg = EchofaceConfig()
    checks = run_doctor(cfg)
    assert isinstance(checks, list)
    assert all(isinstance(c, Check) for c in checks)
    assert len(checks) > 0
