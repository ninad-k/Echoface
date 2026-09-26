"""Idempotent patch script for the vendored OpenTalker/SadTalker checkout,
applied by scripts/setup_windows.ps1 right after cloning. See
vendor/patches/sadtalker_numpy2_compat.patch for the full diff + rationale
for each of these three NumPy 2.x compatibility fixes.

Usage:
    python vendor/patches/patch_sadtalker.py <path-to-vendor-SadTalker-checkout>
"""
from __future__ import annotations

import sys
from pathlib import Path


def _replace_once(path: Path, old: str, new: str, label: str) -> None:
    content = path.read_text(encoding="utf-8")
    if new in content:
        print(f"{label}: already patched, skipping")
        return
    if old not in content:
        raise RuntimeError(f"{label}: expected pattern not found in {path}; SadTalker's source may have changed")
    path.write_text(content.replace(old, new), encoding="utf-8")
    print(f"{label}: patched {path}")


def patch_face3d_preprocess(root: Path) -> None:
    path = root / "src" / "face3d" / "util" / "preprocess.py"
    _replace_once(
        path,
        'warnings.filterwarnings("ignore", category=np.VisibleDeprecationWarning)',
        'warnings.filterwarnings("ignore", category=DeprecationWarning)',
        "face3d/util/preprocess.py (removed np.VisibleDeprecationWarning)",
    )
    _replace_once(
        path,
        "    left = (w/2 - target_size/2 + float((t[0] - w0/2)*s)).astype(np.int32)\n"
        "    right = left + target_size\n"
        "    up = (h/2 - target_size/2 + float((h0/2 - t[1])*s)).astype(np.int32)",
        "    left = (w/2 - target_size/2 + np.asarray((t[0] - w0/2)*s).item()).astype(np.int32)\n"
        "    right = left + target_size\n"
        "    up = (h/2 - target_size/2 + np.asarray((h0/2 - t[1])*s).item()).astype(np.int32)",
        "face3d/util/preprocess.py (resize_n_crop_img float(ndarray))",
    )
    _replace_once(
        path,
        "trans_params = np.array([w0, h0, s, t[0], t[1]])",
        "trans_params = np.array([w0, h0, s, np.asarray(t[0]).item(), np.asarray(t[1]).item()])",
        "face3d/util/preprocess.py (align_img trans_params ragged array)",
    )


def patch_my_awing_arch(root: Path) -> None:
    path = root / "src" / "face3d" / "util" / "my_awing_arch.py"
    _replace_once(
        path,
        "preds = preds.astype(np.float, copy=False)",
        "preds = preds.astype(np.float64, copy=False)",
        "face3d/util/my_awing_arch.py (removed np.float alias)",
    )


def patch_utils_preprocess(root: Path) -> None:
    path = root / "src" / "utils" / "preprocess.py"
    _replace_once(
        path,
        "trans_params = np.array([float(item) for item in np.hsplit(trans_params, 5)]).astype(np.float32)",
        "trans_params = np.array([np.asarray(item).item() for item in np.hsplit(trans_params, 5)]).astype(np.float32)",
        "utils/preprocess.py (hsplit float(ndarray))",
    )


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: patch_sadtalker.py <vendor-SadTalker-checkout-dir>", file=sys.stderr)
        return 1
    root = Path(sys.argv[1])
    patch_face3d_preprocess(root)
    patch_my_awing_arch(root)
    patch_utils_preprocess(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
