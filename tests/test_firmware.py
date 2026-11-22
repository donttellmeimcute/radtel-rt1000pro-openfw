import struct

import pytest

from rt1000pro import FLASH_BASE, FLASH_SIZE
from rt1000pro.firmware import (
    FirmwareError,
    decode_intel_hex,
    encode_intel_hex,
    extract_updater,
    inspect_image,
)


def blank_image() -> bytearray:
    image = bytearray(FLASH_SIZE)
    struct.pack_into("<II", image, 0, 0x2000AEC8, FLASH_BASE | 1)
    return image


def test_hex_round_trip():
    original = bytes(blank_image())
    encoded = encode_intel_hex(original)
    decoded, records = decode_intel_hex(encoded)
    assert decoded == original
    assert records == FLASH_SIZE // 16 + 5  # datos + 4 extensiones lineales + EOF  # datos + extensión lineal + EOF
    assert inspect_image(decoded).initial_sp == 0x2000AEC8


def test_hex_rejects_bad_checksum():
    encoded = encode_intel_hex(bytes(blank_image()))
    damaged = encoded.replace(":020000040800F2", ":020000040800F3", 1)
    with pytest.raises(FirmwareError, match="checksum"):
        decode_intel_hex(damaged)


def test_extract_updater_from_utf16_resource(tmp_path):
    original = bytes(blank_image())
    encoded = encode_intel_hex(original).replace("\n", "")
    payload = encoded.encode("utf-16le") + b"\x00\x00"
    updater = tmp_path / "synthetic.exe"
    updater.write_bytes(b"MZ synthetic" + payload + b"trailer")
    extracted, text, records = extract_updater(updater)
    assert extracted == original
    assert text == encoded
    assert records == FLASH_SIZE // 16 + 5  # datos + 4 extensiones lineales + EOF


def test_image_rejects_bad_size():
    with pytest.raises(FirmwareError, match="Tamaño"):
        inspect_image(b"\x00" * 100)
