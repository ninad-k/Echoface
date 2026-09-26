# ADR-0003: Python 3.14 and CUDA 12.8 (cu128) torch builds

## Status
Accepted.

## Context
The original spec targeted Python 3.10 (the safe, well-trodden version
for this class of ML research code at the time). The verification
machine, however, has Python 3.14 as its default/only readily-available
interpreter, and its GPU is an NVIDIA RTX 5070 Laptop (Blackwell
architecture, compute capability sm_120). Blackwell requires a torch build
compiled against CUDA 12.8 or newer — the cu121/cu124 wheel indexes
produce a torch that either fails to initialize CUDA or silently runs on
CPU on this GPU.

## Decision
Target Python 3.14 for all three venvs, and pin the CUDA wheel index to
`https://download.pytorch.org/whl/cu128` (torch 2.11.0+cu128 at time of
writing). This was verified feasible before committing to it: every heavy
dependency (torch, torchvision, opencv-python, librosa, numba, scikit-image,
faster-whisper/ctranslate2, GFPGAN/basicsr, coqui-tts) has either a native
cp314 wheel or is pure-Python, with the sole exception of `basicsr`, whose
PyPI sdist fails to *build* on Python 3.13+ for reasons unrelated to
Python 3.14 specifically (see ADR text below) and is fixed with a small,
documented patch.

## Consequences
- **Positive**: no downgrade needed; the machine's actual Python install
  works for the whole stack. `torch.cuda.get_device_capability(0)` returns
  `(12, 0)` and real GPU tensor ops succeed.
- **Negative**: Python 3.14 and several of these dependency versions are
  very new (weeks to months old at time of writing) — less community
  troubleshooting history exists than for the 3.10 the spec assumed. Two
  vendor repos (Wav2Lip, SadTalker) needed small NumPy-2.x compatibility
  patches as a direct consequence of moving off their originally-pinned
  ancient dependency versions (NumPy 1.17–1.23), not specifically because
  of Python 3.14 — but the version jump surfaces them.
- **basicsr specifically**: its `setup.py` reads its own generated version
  file via `exec(...)` into a function's `locals()`, then reads that
  `locals()` dict back — a pattern that relied on a CPython implementation
  detail that PEP 667 ("consistent `locals()` semantics", finalized
  3.13) closes. Fixed by a 2-line patch reading the version file with a
  plain string parse instead (`vendor/patches/patch_basicsr.py`).
