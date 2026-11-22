"""Parches mínimos, versionados y verificados para la imagen 260611."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json

from . import FLASH_BASE, STOCK_260611_SHA256
from .firmware import FirmwareError, inspect_image

PATCHED_260611_OPEN_RX_SHA256 = "7f98fe67741f025c31718c804d6a7f112fa34a5b7d97fc7ddc3da0666397fcd4"
PATCHED_260611_AIRBAND_TX_SHA256 = "54d740bc045987f5f42ca3faa13c796c9b308470ef8c22a2df924af44964f8cb"
PATCHED_260611_OPEN_RX_AIRBAND_TX_SHA256 = "31acf6d6426043a58eb6b53433e110db7ccab07eb9cbf2344963404eda8ee9e3"

# Versiones 0.2/0.3: interpretaban incorrectamente el valor de retorno del validador.
REVOKED_SHA256 = {
    "9091d7e7d3d96dfec07150cff07b7de180987b9f0b71b60a8f30820f608f667c",
    "b9ebdb8ebec047c8a1a1fe0902d663fdb26ef936e4cf05443f876942ffc203b9",
}


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


AIRBAND_TX_MARKER_PATCH = Patch(
    name="airband-tx-marker-check",
    address=0x0800810E,
    expected_hex="07d0",
    replacement_hex="00bf",
    description=(
        "Sustituye BEQ por NOP para que el marcador interno del modo aeronáutico "
        "no desvíe el camino 108–136 MHz a la tabla general."
    ),
)

AIRBAND_TX_RETURN_PATCH = Patch(
    name="airband-tx-not-out-of-range",
    address=0x0800811C,
    expected_hex="0020",
    replacement_hex="0120",
    description=(
        "Cambia MOVS R0,#0 por MOVS R0,#1 en el camino 108–136 MHz. "
        "Los llamadores confirman que cero significa 'out of range' y bloqueo; "
        "uno permite continuar, sujeto a los demás interbloqueos independientes."
    ),
)

AIRBAND_TX_PATCHES = (AIRBAND_TX_MARKER_PATCH, AIRBAND_TX_RETURN_PATCH)

OPEN_RX_PATCHES = (
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
            "permite continuar en los diálogos de acceso restringido."
        ),
    ),
)

PROFILES: dict[str, tuple[Patch, ...]] = {
    "airband-tx": AIRBAND_TX_PATCHES,
    "open-rx": OPEN_RX_PATCHES,
    "open-rx-airband-tx": OPEN_RX_PATCHES + AIRBAND_TX_PATCHES,
}

PATCHED_SHA256 = {
    "airband-tx": PATCHED_260611_AIRBAND_TX_SHA256,
    "open-rx": PATCHED_260611_OPEN_RX_SHA256,
    "open-rx-airband-tx": PATCHED_260611_OPEN_RX_AIRBAND_TX_SHA256,
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
    if digest in REVOKED_SHA256:
        raise FirmwareError("Esta imagen Airband anterior está retirada; regenera desde el firmware original")
    if digest in PATCHED_SHA256.values():
        raise FirmwareError("La imagen ya contiene uno de los perfiles conocidos")
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
    if expected_sha256 == STOCK_260611_SHA256 and sha256(output).hexdigest() != PATCHED_SHA256[profile]:
        raise FirmwareError("La variante no coincide con el hash reproducible documentado")
    return output


def manifest(profile: str = "open-rx") -> str:
    if profile not in PROFILES:
        raise FirmwareError(f"Perfil desconocido: {profile}")
    document = {
        "format": 1,
        "profile": profile,
        "stock_sha256": STOCK_260611_SHA256,
        "patched_sha256": PATCHED_SHA256[profile],
        "patches": [asdict(patch) for patch in PROFILES[profile]],
    }
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"
