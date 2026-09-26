from pathlib import Path

import pytest

from echoface.util.proc import echoface_home, resolve_asset, resolve_exe


@pytest.fixture(autouse=True)
def _no_ambient_echoface_home(monkeypatch):
    """None of these tests should be affected by whatever the real
    session's ECHOFACE_HOME happens to be set to."""
    monkeypatch.delenv("ECHOFACE_HOME", raising=False)


def test_resolve_exe_resolves_existing_relative_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "sub").mkdir()
    exe = tmp_path / "sub" / "fake.exe"
    exe.write_text("not a real exe")

    resolved = resolve_exe("sub/fake.exe")
    assert Path(resolved).is_absolute()
    assert Path(resolved) == exe.resolve()


def test_resolve_exe_leaves_path_on_path_unchanged(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # "ffmpeg" doesn't exist relative to cwd, so it must be returned as-is
    # so shutil.which / PATH lookup still works downstream.
    assert resolve_exe("ffmpeg") == "ffmpeg"


def test_resolve_exe_leaves_absolute_path_unchanged(tmp_path):
    abs_path = str(tmp_path / "does_not_exist.exe")
    assert resolve_exe(abs_path) == abs_path


def test_echoface_home_unset_returns_none(monkeypatch):
    monkeypatch.delenv("ECHOFACE_HOME", raising=False)
    assert echoface_home() is None


def test_echoface_home_blank_returns_none(monkeypatch):
    monkeypatch.setenv("ECHOFACE_HOME", "   ")
    assert echoface_home() is None


def test_echoface_home_set_returns_path(tmp_path, monkeypatch):
    monkeypatch.setenv("ECHOFACE_HOME", str(tmp_path))
    assert echoface_home() == tmp_path


def test_resolve_asset_prefers_base_over_echoface_home(tmp_path, monkeypatch):
    """When the file exists under `base` (the checkout), that wins --
    the code/asset under test always comes from the checkout first."""
    base_dir = tmp_path / "checkout"
    home_dir = tmp_path / "provisioned"
    base_dir.mkdir()
    home_dir.mkdir()
    (base_dir / "models").mkdir()
    (base_dir / "models" / "x.pth").write_bytes(b"from checkout")
    (home_dir / "models").mkdir()
    (home_dir / "models" / "x.pth").write_bytes(b"from home")
    monkeypatch.setenv("ECHOFACE_HOME", str(home_dir))

    resolved = resolve_asset("models/x.pth", base=base_dir)
    assert resolved == (base_dir / "models" / "x.pth").resolve()


def test_resolve_asset_falls_back_to_echoface_home_when_missing_from_base(tmp_path, monkeypatch):
    """When the file does NOT exist under `base` (e.g. a self-hosted CI
    runner's ephemeral checkout, which has no envs/models/vendor), fall
    back to ECHOFACE_HOME."""
    base_dir = tmp_path / "checkout"
    home_dir = tmp_path / "provisioned"
    base_dir.mkdir()
    home_dir.mkdir()
    (home_dir / "models").mkdir()
    (home_dir / "models" / "x.pth").write_bytes(b"from home")
    monkeypatch.setenv("ECHOFACE_HOME", str(home_dir))

    resolved = resolve_asset("models/x.pth", base=base_dir)
    assert resolved == (home_dir / "models" / "x.pth").resolve()


def test_resolve_asset_returns_base_relative_path_when_found_nowhere(tmp_path, monkeypatch):
    """Even when the file exists at neither location, the result must
    still be an absolute path (base-relative) -- never a bare relative
    string -- so a downstream subprocess call with an explicit cwd gets
    a clear file-not-found instead of a silently-wrong argument."""
    base_dir = tmp_path / "checkout"
    base_dir.mkdir()
    monkeypatch.delenv("ECHOFACE_HOME", raising=False)

    resolved = resolve_asset("models/nope.pth", base=base_dir)
    assert resolved == (base_dir / "models" / "nope.pth").resolve()
    assert resolved.is_absolute()


def test_resolve_asset_leaves_absolute_path_unchanged(tmp_path):
    abs_path = tmp_path / "already_absolute.pth"
    assert resolve_asset(str(abs_path)) == abs_path


def test_resolve_exe_falls_back_to_echoface_home(tmp_path, monkeypatch):
    """resolve_exe (used for venv interpreters/executables) gets the
    same ECHOFACE_HOME fallback as resolve_asset, transparently."""
    base_dir = tmp_path / "checkout"
    home_dir = tmp_path / "provisioned"
    base_dir.mkdir()
    (home_dir / "envs" / "face" / "Scripts").mkdir(parents=True)
    exe = home_dir / "envs" / "face" / "Scripts" / "python.exe"
    exe.write_text("not a real exe")
    monkeypatch.setenv("ECHOFACE_HOME", str(home_dir))
    monkeypatch.chdir(base_dir)

    resolved = resolve_exe("envs/face/Scripts/python.exe")
    assert Path(resolved) == exe.resolve()
