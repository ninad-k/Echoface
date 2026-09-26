"""Pure-numpy region masking/blending for face restoration (GFPGAN,
CodeFormer). Shared by both scripts/gfpgan_runner.py and
scripts/codeformer_runner.py so `face.restore_region: face | mouth`
behaves identically regardless of which restorer produced the pixels.

No cv2/torch dependency, so this is unit-testable from the orchestrator
venv (`echoface`'s own venv has numpy transitively via faster-whisper,
but not opencv) without needing envs\\face.
"""

from __future__ import annotations

import numpy as np

VALID_REGIONS = ("face", "mouth")


def mouth_region_mask(height: int, width: int, feather: float = 0.12) -> np.ndarray:
    """Build a soft (0..1) mask over an aligned face crop (as produced by
    GFPGAN's/CodeFormer's face-alignment helpers, typically a roughly
    frontal, roughly centred crop) that is 1.0 over the lower-center
    "mouth" region and fades to 0.0 elsewhere, via a separable smoothstep
    feather rather than a hard rectangle — avoids a visible seam at the
    region boundary.

    Box (as a fraction of height/width, tuned for a standard face-crop
    aspect where the mouth sits in the lower-middle third): y in
    [0.55, 0.92], x in [0.22, 0.78]. `feather` is the fraction of the
    smaller dimension used as the fade-in/out distance on every edge.
    """
    if height <= 0 or width <= 0:
        raise ValueError("height and width must be positive")

    y0, y1 = 0.55, 0.92
    x0, x1 = 0.22, 0.78
    feather_px = max(1.0, feather * min(height, width))

    ys = np.arange(height, dtype=np.float64)
    xs = np.arange(width, dtype=np.float64)

    def _edge(coord: np.ndarray, lo: float, hi: float, size: int) -> np.ndarray:
        lo_px, hi_px = lo * size, hi * size
        # Smooth ramp up over [lo_px - feather, lo_px], flat 1 over
        # [lo_px, hi_px], smooth ramp down over [hi_px, hi_px + feather].
        rise = np.clip((coord - (lo_px - feather_px)) / feather_px, 0.0, 1.0)
        fall = np.clip(((hi_px + feather_px) - coord) / feather_px, 0.0, 1.0)
        return np.minimum(rise, fall)

    y_profile = _edge(ys, y0, y1, height)
    x_profile = _edge(xs, x0, x1, width)
    mask = np.outer(y_profile, x_profile)
    return mask.astype(np.float32)


def blend_region(
    original: np.ndarray,
    restored: np.ndarray,
    region: str,
    feather: float = 0.12,
) -> np.ndarray:
    """Blend `restored` over `original` (both HxWx3 uint8 arrays, same
    shape — the aligned face crop before paste-back) according to
    `region`:
      - "face": return `restored` unchanged (the historical/default
        behaviour — restore the whole detected face).
      - "mouth": blend only the lower-center mouth region using a
        feathered mask (`mouth_region_mask`), leaving the rest of the
        crop as `original` so restoration artefacts elsewhere in the face
        (eyes, forehead) can't appear.
    """
    if region not in VALID_REGIONS:
        raise ValueError(f"region must be one of {VALID_REGIONS}, got {region!r}")
    if original.shape != restored.shape:
        raise ValueError(f"original/restored shape mismatch: {original.shape} vs {restored.shape}")
    if region == "face":
        return restored

    h, w = original.shape[:2]
    mask = mouth_region_mask(h, w, feather=feather)
    mask3 = mask[:, :, None] if original.ndim == 3 else mask
    blended = original.astype(np.float32) * (1 - mask3) + restored.astype(np.float32) * mask3
    return np.clip(blended, 0, 255).astype(original.dtype)
