import struct

import pytest

from rt1000pro import FLASH_BASE, FLASH_SIZE, STOCK_260611_SHA256
from rt1000pro.firmware import FirmwareError
from rt1000pro.patches import PROFILES, apply_profile, manifest


def compatible_blank() -> bytes:
    image = bytearray(FLASH_SIZE)
    struct.pack_into("<II", image, 0, 0x2000AEC8, FLASH_BASE | 1)
    unique_patches = {patch for patches in PROFILES.values() for patch in patches}
    for patch in unique_patches:
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



def test_airband_patch_is_specific_and_composable():
    original = compatible_blank()
    airband = apply_profile(original, "airband-tx", expected_sha256=None)
    patches = PROFILES["airband-tx"]
    expected = sorted(
        patch.offset + index
        for patch in patches
        for index, (a, b) in enumerate(zip(patch.expected, patch.replacement))
        if a != b
    )
    assert [i for i, (a, b) in enumerate(zip(original, airband)) if a != b] == expected
    assert all(airband[p.offset:p.offset + 2] == p.replacement for p in patches)

    combined = apply_profile(original, "open-rx-airband-tx", expected_sha256=None)
    expected_combined = bytearray(apply_profile(original, "open-rx", expected_sha256=None))
    for patch in patches:
        expected_combined[patch.offset:patch.offset + 2] = patch.replacement
    assert combined == bytes(expected_combined)
    assert '"profile": "airband-tx"' in manifest("airband-tx")
