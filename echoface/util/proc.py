"""Subprocess helper: resolve a possibly-relative venv executable path to an
absolute one.

On Windows, ``subprocess.run([exe, ...])`` resolves ``exe`` via
``CreateProcess``'s ``lpApplicationName``, which does *not* search relative
to the current working directory the way a shell would — a relative path
like ``envs/face/Scripts/python.exe`` reliably raises
``FileNotFoundError: [WinError 2]`` even when that file exists under the
process's cwd. All of our config defaults (``face.device`` python_exe,
``voice.piper_exe``, etc.) are written as repo-relative paths for
readability, so every call site that shells into a venv must resolve them
first — this is that one place to do it.
"""

from __future__ import annotations

from pathlib import Path


def resolve_exe(path: str) -> str:
    """Return an absolute path for `path` if it exists relative to the
    current working directory; otherwise return it unchanged (so bare
    commands meant to be found on PATH, e.g. "ffmpeg", still work)."""
    p = Path(path)
    if not p.is_absolute():
        candidate = Path.cwd() / p
        if candidate.exists():
            return str(candidate.resolve())
    return path
