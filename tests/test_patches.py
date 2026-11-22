import struct

import pytest

from rt1000pro import FLASH_BASE, FLASH_SIZE, STOCK_260611_SHA256
from rt1000pro.firmware import FirmwareError
from rt1000pro.patches import PROFILES, apply_profile, manifest


def compatible_blank() -> bytes:
    image = bytearray(FLASH_SIZE)
    struct.pack_into("<II", image, 0, 0x2000AEC8, FLASH_BASE | 1)
    for patch in PROFILES["open-rx"]:
        image[patch.offset:patch.offset + len(patch.expected)] = patch.expected
    return bytes(image)


def test_patch_changes_only_declared_bytes():
    original = compatible_blank()
    patched = apply_profile(original, expected_sha256=None)
    differences = [i for i, (a, b) in enumerate(zip(original, patched)) if a != b]
    expected = sorted(
        patch.offset + index
        for patch in PROFILES["open-rx"]
        for index, (a, b) in enumerate(zip(patch.expected, patch.replacement))
        if a != b
    )
    assert differences == expected
    assert all(patched[p.offset:p.offset + 2] == p.replacement for p in PROFILES["open-rx"])


def test_patch_rejects_unexpected_instruction():
    original = bytearray(compatible_blank())
    original[PROFILES["open-rx"][0].offset] ^= 0xFF
    with pytest.raises(FirmwareError, match="bytes inesperados"):
        apply_profile(bytes(original), expected_sha256=None)


def test_patch_is_hash_locked_by_default():
    with pytest.raises(FirmwareError, match="Hash incompatible"):
        apply_profile(compatible_blank())
    assert STOCK_260611_SHA256 in manifest()
