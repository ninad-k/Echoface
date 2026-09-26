"""Patch script for basicsr==1.4.2's sdist, applied by scripts/setup_windows.ps1
before building/installing it into envs\\face.

basicsr is unmaintained (last PyPI release 2022) and breaks with modern
tooling in two ways we hit on this machine (Python 3.14, torchvision
0.26, setuptools 78):

1. setup.py's get_version() does:
       exec(compile(f.read(), version_file, 'exec'))
       return locals()['__version__']
   Under CPython 3.13+ (PEP 667 - consistent locals() semantics), a
   function-scope exec() no longer reliably mutates what locals() returns,
   so this raises ``KeyError: '__version__'`` and the wheel build fails
   before basicsr is even installed. Fixed by reading the generated
   version file with a simple line parse instead of exec+locals().

2. basicsr/data/degradations.py imports
       from torchvision.transforms.functional_tensor import rgb_to_grayscale
   ``functional_tensor`` was removed in torchvision 0.17+; the function
   moved to ``torchvision.transforms.functional``. This is a well-known
   basicsr/GFPGAN break with any modern torchvision (not specific to
   Python 3.14) — fixed by repointing the import.

Usage (see scripts/setup_windows.ps1 for the full download+patch+install
sequence):
    python vendor/patches/patch_basicsr.py <path-to-extracted-basicsr-1.4.2>
"""
from __future__ import annotations

import sys
from pathlib import Path


def patch_setup_py(root: Path) -> None:
    path = root / "setup.py"
    content = path.read_text(encoding="utf-8")
    old = (
        "def get_version():\n"
        "    with open(version_file, 'r') as f:\n"
        "        exec(compile(f.read(), version_file, 'exec'))\n"
        "    return locals()['__version__']"
    )
    new = (
        "def get_version():\n"
        "    with open(version_file, 'r') as f:\n"
        "        for line in f:\n"
        "            if line.startswith('__version__'):\n"
        "                return line.split('=', 1)[1].strip().strip(\"'\\\"\")\n"
        "    raise RuntimeError(f'could not find __version__ in {version_file}')"
    )
    if old not in content:
        if "for line in f:" in content:
            print("basicsr setup.py already patched, skipping")
            return
        raise RuntimeError("basicsr setup.py get_version() block not found; repo layout may have changed")
    path.write_text(content.replace(old, new), encoding="utf-8")
    print(f"patched {path}")


def patch_degradations_py(root: Path) -> None:
    path = root / "basicsr" / "data" / "degradations.py"
    content = path.read_text(encoding="utf-8")
    old = "from torchvision.transforms.functional_tensor import rgb_to_grayscale"
    new = "from torchvision.transforms.functional import rgb_to_grayscale"
    if old not in content:
        if new in content:
            print("basicsr degradations.py already patched, skipping")
            return
        raise RuntimeError("basicsr degradations.py functional_tensor import not found; repo layout may have changed")
    path.write_text(content.replace(old, new), encoding="utf-8")
    print(f"patched {path}")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: patch_basicsr.py <extracted-basicsr-source-dir>", file=sys.stderr)
        return 1
    root = Path(sys.argv[1])
    patch_setup_py(root)
    patch_degradations_py(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
