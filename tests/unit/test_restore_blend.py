"""Unit tests for echoface.util.restore_blend: the mouth-region mask and
face/mouth restoration blending used by both the GFPGAN and CodeFormer
runners (face.restore_region config)."""

from __future__ import annotations

import numpy as np
import pytest

from echoface.util.restore_blend import blend_region, mouth_region_mask


def test_mouth_region_mask_shape_and_range():
    mask = mouth_region_mask(512, 512)
    assert mask.shape == (512, 512)
    assert mask.min() >= 0.0
    assert mask.max() <= 1.0 + 1e-6


def test_mouth_region_mask_center_is_hot_corners_are_cold():
    mask = mouth_region_mask(512, 512)
    # Center of the mouth box (~ y=0.73*512, x=0.5*512) should be ~1.0.
    assert mask[380, 256] > 0.9
    # Top-left corner (forehead/hair region) should be ~0.
    assert mask[10, 10] < 0.05
    # Top-center (forehead) should also be near 0 - mouth mask shouldn't
    # touch the upper half of the crop at all.
    assert mask[50, 256] < 0.05


def test_mouth_region_mask_rejects_bad_dims():
    with pytest.raises(ValueError):
        mouth_region_mask(0, 100)
    with pytest.raises(ValueError):
        mouth_region_mask(100, -5)


def test_blend_region_face_returns_restored_unchanged():
    original = np.zeros((64, 64, 3), dtype=np.uint8)
    restored = np.full((64, 64, 3), 200, dtype=np.uint8)
    out = blend_region(original, restored, region="face")
    assert np.array_equal(out, restored)


def test_blend_region_mouth_keeps_top_as_original():
    original = np.zeros((512, 512, 3), dtype=np.uint8)
    restored = np.full((512, 512, 3), 255, dtype=np.uint8)
    out = blend_region(original, restored, region="mouth")
    # Top of the crop (forehead) should remain close to original (0).
    assert out[20, 256, 0] < 10
    # Mouth-region center should be close to restored (255).
    assert out[380, 256, 0] > 240


def test_blend_region_mouth_output_dtype_and_shape_preserved():
    original = np.random.randint(0, 255, (128, 128, 3), dtype=np.uint8)
    restored = np.random.randint(0, 255, (128, 128, 3), dtype=np.uint8)
    out = blend_region(original, restored, region="mouth")
    assert out.dtype == original.dtype
    assert out.shape == original.shape


def test_blend_region_rejects_unknown_region():
    a = np.zeros((32, 32, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        blend_region(a, a, region="ears")


def test_blend_region_rejects_shape_mismatch():
    a = np.zeros((32, 32, 3), dtype=np.uint8)
    b = np.zeros((16, 16, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        blend_region(a, b, region="mouth")
