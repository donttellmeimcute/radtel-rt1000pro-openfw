"""Parches mínimos, versionados y verificados para la imagen 260611."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json

from . import FLASH_BASE, STOCK_260611_SHA256
from .firmware import FirmwareError, inspect_image

PATCHED_260611_OPEN_RX_SHA256 = "7f98fe67741f025c31718c804d6a7f112fa34a5b7d97fc7ddc3da0666397fcd4"


@dataclass(frozen=True)
class Patch:
    name: str
    address: int
    expected_hex: str
    replacement_hex: str
    description: str

    @property
    def offset(self) -> int:
        return self.address - FLASH_BASE

    @property
    def expected(self) -> bytes:
        return bytes.fromhex(self.expected_hex)

    @property
    def replacement(self) -> bytes:
        return bytes.fromhex(self.replacement_hex)


PROFILES: dict[str, tuple[Patch, ...]] = {
    "open-rx": (
        Patch(
            name="all-band-at-boot",
            address=0x080035E8,
            expected_hex="02d1",
            replacement_hex="00bf",
            description=(
                "Sustituye BNE por NOP tras comparar la tecla de arranque 0x0E; "
                "activa el indicador ALL BAND ya existente en cada arranque."
            ),
        ),
        Patch(
            name="restricted-menu-access",
            address=0x080080B8,
            expected_hex="acd0",
            replacement_hex="00bf",
            description=(
                "Sustituye BEQ por NOP después de la comparación de 16 bytes; "
                "permite continuar en los diálogos de acceso restringido. No altera "
                "las validaciones de frecuencia, potencia ni la función Prohibit TX."
            ),
        ),
    ),
}


def apply_profile(
    image: bytes,
    profile: str = "open-rx",
    *,
    expected_sha256: str | None = STOCK_260611_SHA256,
) -> bytes:
    """Aplica un perfil; por defecto exige el hash exacto de la versión 260611."""
    inspect_image(image)
    if profile not in PROFILES:
        raise FirmwareError(f"Perfil desconocido: {profile}")
    digest = sha256(image).hexdigest()
    if digest == PATCHED_260611_OPEN_RX_SHA256:
        raise FirmwareError("La imagen ya contiene el perfil open-rx")
    if expected_sha256 is not None and digest != expected_sha256:
        raise FirmwareError(
            "Hash incompatible; el parche está bloqueado a la imagen 260611: "
            f"obtenido {digest}, esperado {expected_sha256}"
        )
    result = bytearray(image)
    for patch in PROFILES[profile]:
        start = patch.offset
        end = start + len(patch.expected)
        actual = bytes(result[start:end])
        if actual != patch.expected:
            raise FirmwareError(
                f"{patch.name}: bytes inesperados en 0x{patch.address:08X}: "
                f"{actual.hex()} != {patch.expected_hex}"
            )
        if len(patch.expected) != len(patch.replacement):
            raise FirmwareError(f"{patch.name}: el parche cambia el tamaño del código")
        result[start:end] = patch.replacement
    output = bytes(result)
    inspect_image(output)
    return output


def manifest(profile: str = "open-rx") -> str:
    if profile not in PROFILES:
        raise FirmwareError(f"Perfil desconocido: {profile}")
    document = {
        "format": 1,
        "profile": profile,
        "stock_sha256": STOCK_260611_SHA256,
        "patched_sha256": PATCHED_260611_OPEN_RX_SHA256,
        "patches": [asdict(patch) for patch in PROFILES[profile]],
    }
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"
