"""Pins facexlib/GFPGAN's model-weight resolution to an absolute path
under `models/gfpgan/` (where `detection_Resnet50_Final.pth` and
`parsing_parsenet.pth` already live per `models/MODELS.md`), instead of
the cwd-relative `'gfpgan/weights'` default hardcoded inside the
installed `gfpgan` package (`gfpgan/utils.py`'s
`FaceRestoreHelper(..., model_rootpath='gfpgan/weights')`) and SadTalker's
own `--enhancer gfpgan` path (`src/utils/face_enhancer.py`) and safe
keypoint extractor (`src/face3d/extract_kp_videos_safe.py`), both of
which go through the same installed `facexlib` package.

That relative `model_rootpath` is passed straight through to
`facexlib.utils.misc.load_file_from_url(..., save_dir=model_rootpath)`,
which does `os.makedirs(save_dir, exist_ok=True)` on it *as given* (no
package-relative `ROOT_DIR` join, unlike facexlib's own `model_dir`
default) -- so it resolves against the current process's cwd. Whenever
a runner subprocess's cwd is the repo root (the common case), this
creates a stray `gfpgan/weights/` directory there, which can then shadow
the real `gfpgan` package for tools that inspect `sys.path` (e.g. mypy).
See docs/qa/defect-log.md's DEF-13 for the full incident.

`init_detection_model`/`init_parsing_model` in `facexlib.detection`/
`facexlib.parsing` look up `load_file_from_url` as a module-global at
call time (not a bound default), so overwriting that attribute on each
already-imported module -- as done here -- reliably intercepts every
caller that goes through them, regardless of what `model_rootpath`/
`model_dir` string they pass in.

Call `pin_facexlib_weights_dir()` once, before constructing `GFPGANer`
or calling anything from `facexlib.detection`/`facexlib.parsing`, in
any subprocess runner that touches them.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_FACEXLIB_WEIGHTS_DIR = REPO_ROOT / "models" / "gfpgan"


def pin_facexlib_weights_dir(weights_dir: Path | None = None) -> Path:
    """Monkeypatch facexlib's detection/parsing model loaders so every
    weight file resolves under an absolute directory (default:
    models/gfpgan/) instead of whatever cwd-relative path the caller
    passed as model_rootpath/model_dir. Returns the resolved directory
    (also created if missing) for callers that want to assert on it."""
    target_dir = weights_dir or DEFAULT_FACEXLIB_WEIGHTS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    def _pinned_load_file_from_url(
        url: str,
        model_dir: str | None = None,  # noqa: ARG001 - intentionally ignored, see module docstring
        progress: bool = True,
        file_name: str | None = None,
        save_dir: str | None = None,  # noqa: ARG001 - intentionally ignored, see module docstring
    ) -> str:
        filename = file_name or Path(urlparse(url).path).name
        cached_file = target_dir / filename
        if not cached_file.exists():
            from torch.hub import download_url_to_file

            download_url_to_file(url, str(cached_file), hash_prefix=None, progress=progress)
        return str(cached_file)

    import facexlib.detection as _det_mod
    import facexlib.parsing as _parse_mod

    _det_mod.load_file_from_url = _pinned_load_file_from_url
    _parse_mod.load_file_from_url = _pinned_load_file_from_url
    return target_dir
