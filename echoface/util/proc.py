"""Subprocess helpers: resolve a possibly-relative venv executable or asset
path to an absolute one, optionally falling back to a separately-provisioned
install directory.

On Windows, ``subprocess.run([exe, ...])`` resolves ``exe`` via
``CreateProcess``'s ``lpApplicationName``, which does *not* search relative
to the current working directory the way a shell would — a relative path
like ``envs/face/Scripts/python.exe`` reliably raises
``FileNotFoundError: [WinError 2]`` even when that file exists under the
process's cwd. All of our config defaults (``face.device`` python_exe,
``voice.piper_exe``, etc.) are written as repo-relative paths for
readability, so every call site that shells into a venv must resolve them
first — this is that one place to do it.

``ECHOFACE_HOME``: on a self-hosted CI runner, the checkout (where the code
under test lives — ``echoface/``, ``scripts/``, ``tests/``) is an ephemeral
``_work`` folder that does *not* contain the heavy, separately-provisioned
``envs/``, ``models/``, or ``vendor/`` directories (those are gigabytes of
venvs and model weights — provisioned once on the machine via
``scripts/setup_windows.ps1``, not re-created per run). Setting
``ECHOFACE_HOME`` to that provisioned install's path (e.g.
``D:\\PProjects\\Echoface``) lets ``resolve_asset``/``resolve_exe`` fall
back to it for anything not found under the current working directory,
while the code itself always still comes from the checkout (since a
checked-in script like ``scripts/gfpgan_runner.py`` *does* exist under cwd
there, that branch is taken first and ``ECHOFACE_HOME`` is never consulted
for it). Unset (the default, and every non-CI-runner use), behaviour is
identical to before this variable existed. See
``docs/ops/self-hosted-gpu-runner.md``.
"""

from __future__ import annotations

import os
from pathlib import Path


def echoface_home() -> Path | None:
    """The `ECHOFACE_HOME` env var as a `Path`, if set to a non-empty
    value, else `None`. Existence of the directory is NOT checked here
    — callers decide what (if anything) they need to find inside it."""
    value = os.environ.get("ECHOFACE_HOME", "").strip()
    return Path(value) if value else None


def resolve_asset(rel_path: str, base: Path | None = None) -> Path:
    """Resolve a repo-relative path (a venv executable, a model weight
    file, a checked-in script, ...) to an absolute `Path`.

    Tries `base` (default: the current working directory) first — the
    common case of a single, fully-provisioned checkout where the code
    and its assets live together — then falls back to `$ECHOFACE_HOME`
    if that env var is set and the path exists there instead.

    Always returns an absolute path, even when the file exists at
    neither location (the `base`-relative absolute path is returned in
    that case), so callers can pass the result straight into a
    subprocess call with an explicit `cwd` and get a clear
    "file not found" from the subprocess itself rather than a
    silently-wrong relative argument."""
    p = Path(rel_path)
    if p.is_absolute():
        return p
    base = base or Path.cwd()
    primary = (base / p).resolve()
    if primary.exists():
        return primary
    home = echoface_home()
    if home is not None:
        alternate = (home / p).resolve()
        if alternate.exists():
            return alternate
    return primary


def resolve_exe(path: str) -> str:
    """Return an absolute path for `path` if it exists relative to the
    current working directory or (failing that) under `$ECHOFACE_HOME`
    if set; otherwise return it unchanged (so bare commands meant to be
    found on PATH, e.g. "ffmpeg", still work)."""
    p = Path(path)
    if p.is_absolute():
        return path
    resolved = resolve_asset(path)
    if resolved.exists():
        return str(resolved)
    return path
