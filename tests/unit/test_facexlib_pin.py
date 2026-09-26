"""Unit tests for echoface.util.facexlib_pin -- the DEF-13 fix for the
stray gfpgan/ (or weights/, results/) directory that facexlib/GFPGAN's
own cwd-relative default weight path can create at the repo root.

The real `facexlib` package isn't installed in the orchestrator venv
(it only lives in envs\\face), so these tests inject minimal fake
`facexlib.detection`/`facexlib.parsing` modules via sys.modules rather
than requiring the real dependency -- what's under test is the
monkeypatch logic and path resolution, not facexlib itself (that's
covered for real by tests/gpu's gfpgan/codeformer/sadtalker tests)."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from echoface.util.facexlib_pin import DEFAULT_FACEXLIB_WEIGHTS_DIR, pin_facexlib_weights_dir


@pytest.fixture
def fake_facexlib(monkeypatch):
    """Register minimal fake facexlib.detection/facexlib.parsing modules,
    each with a placeholder load_file_from_url attribute, and clean up
    afterward regardless of what the test does to sys.modules."""
    det_mod = types.ModuleType("facexlib.detection")
    parse_mod = types.ModuleType("facexlib.parsing")
    det_mod.load_file_from_url = "unpatched-detection"  # type: ignore[attr-defined]
    parse_mod.load_file_from_url = "unpatched-parsing"  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "facexlib", types.ModuleType("facexlib"))
    monkeypatch.setitem(sys.modules, "facexlib.detection", det_mod)
    monkeypatch.setitem(sys.modules, "facexlib.parsing", parse_mod)
    return det_mod, parse_mod


def test_default_weights_dir_is_models_gfpgan():
    """The default target is models/gfpgan/ -- where the two facexlib
    weight files (detection_Resnet50_Final.pth, parsing_parsenet.pth)
    already live per models/MODELS.md, not a cwd-relative path."""
    assert DEFAULT_FACEXLIB_WEIGHTS_DIR.is_absolute()
    assert DEFAULT_FACEXLIB_WEIGHTS_DIR.parts[-2:] == ("models", "gfpgan")


def test_pin_overwrites_both_detection_and_parsing_loaders(fake_facexlib, tmp_path):
    det_mod, parse_mod = fake_facexlib
    pin_facexlib_weights_dir(weights_dir=tmp_path)

    assert callable(det_mod.load_file_from_url)
    assert callable(parse_mod.load_file_from_url)
    # Both modules must be patched to the *same* function so behaviour
    # (and any future changes to it) stays in sync between detection and
    # parsing model loading.
    assert det_mod.load_file_from_url is parse_mod.load_file_from_url


def test_pin_creates_target_directory(fake_facexlib, tmp_path):
    target = tmp_path / "nested" / "weights_dir"
    assert not target.exists()
    returned = pin_facexlib_weights_dir(weights_dir=target)
    assert returned == target
    assert target.is_dir()


def test_pinned_loader_returns_cached_file_without_download(fake_facexlib, tmp_path):
    """When the weight file already exists under the pinned dir (the
    common case -- setup_windows.ps1 stages it there), the pinned
    loader must return it directly, with no download attempt and no
    directory created anywhere else."""
    det_mod, _ = fake_facexlib
    existing = tmp_path / "detection_Resnet50_Final.pth"
    existing.write_bytes(b"fake weights")

    pin_facexlib_weights_dir(weights_dir=tmp_path)
    result = det_mod.load_file_from_url(
        url="https://github.com/xinntao/facexlib/releases/download/v0.1.0/detection_Resnet50_Final.pth",
        model_dir="gfpgan/weights",  # the cwd-relative value GFPGAN would normally pass
        save_dir="gfpgan/weights",  # ditto -- both must be ignored
    )
    assert Path(result) == existing
    assert not (Path.cwd() / "gfpgan").exists()
