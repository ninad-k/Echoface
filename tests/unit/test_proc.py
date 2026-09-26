from pathlib import Path

from echoface.util.proc import resolve_exe


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
