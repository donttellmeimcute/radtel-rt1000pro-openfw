"""Extracción y conversión de imágenes Intel HEX, sin dependencias externas."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import struct

from . import FLASH_BASE, FLASH_SIZE

_UPDATER_MARKER = ":020000040800F2".encode("utf-16le")
_HEX_ALPHABET = frozenset(b":0123456789ABCDEFabcdef\r\n")


class FirmwareError(ValueError):
    """La entrada no tiene el formato o las propiedades esperadas."""


@dataclass(frozen=True)
class ImageInfo:
    base: int
    size: int
    sha256: str
    initial_sp: int
    reset_vector: int
    records: int | None = None


def _records(text: str):
    """Itera registros Intel HEX concatenados o separados por líneas."""
    compact = "".join(text.split())
    if not compact.startswith(":"):
        raise FirmwareError("El Intel HEX debe comenzar por ':'.")
    for number, encoded in enumerate(compact.split(":")[1:], 1):
        if not encoded:
            continue
        try:
            raw = bytes.fromhex(encoded)
        except ValueError as exc:
            raise FirmwareError(f"Registro {number}: hexadecimal inválido") from exc
        if len(raw) < 5 or len(raw) != raw[0] + 5:
            raise FirmwareError(f"Registro {number}: longitud inválida")
        if sum(raw) & 0xFF:
            raise FirmwareError(f"Registro {number}: checksum inválido")
        yield number, raw


def decode_intel_hex(
    text: str,
    *,
    base: int = FLASH_BASE,
    size: int = FLASH_SIZE,
    fill: int = 0x00,
) -> tuple[bytes, int]:
    """Convierte Intel HEX a una imagen plana y valida límites y checksums."""
    if not 0 <= fill <= 0xFF:
        raise ValueError("fill debe ser un byte")
    memory: dict[int, int] = {}
    upper = 0
    eof = False
    count = 0
    for count, raw in _records(text):
        length = raw[0]
        address = int.from_bytes(raw[1:3], "big")
        kind = raw[3]
        data = raw[4:-1]
        if kind == 0x00:
            absolute = upper + address
            for index, value in enumerate(data):
                location = absolute + index
                if location in memory and memory[location] != value:
                    raise FirmwareError(f"Solapamiento contradictorio en 0x{location:08X}")
                memory[location] = value
        elif kind == 0x01:
            eof = True
        elif kind == 0x02:
            if length != 2:
                raise FirmwareError("Registro de segmento inválido")
            upper = int.from_bytes(data, "big") << 4
        elif kind == 0x04:
            if length != 2:
                raise FirmwareError("Registro de dirección lineal inválido")
            upper = int.from_bytes(data, "big") << 16
        elif kind in (0x03, 0x05):
            pass  # Direcciones de entrada: no afectan al contenido de flash.
        else:
            raise FirmwareError(f"Tipo de registro no soportado: 0x{kind:02X}")
    if not eof:
        raise FirmwareError("Falta el registro de fin de archivo Intel HEX")
    if not memory:
        raise FirmwareError("El Intel HEX no contiene datos")
    minimum, maximum = min(memory), max(memory)
    if minimum < base or maximum >= base + size:
        raise FirmwareError(
            f"Datos fuera de 0x{base:08X}–0x{base + size - 1:08X}: "
            f"0x{minimum:08X}–0x{maximum:08X}"
        )
    image = bytes(memory.get(address, fill) for address in range(base, base + size))
    return image, count


def extract_updater(path: str | Path) -> tuple[bytes, str, int]:
    """Extrae la cadena UTF-16LE integrada en el actualizador .NET 260611."""
    executable = Path(path).read_bytes()
    start = executable.find(_UPDATER_MARKER)
    if start < 0:
        raise FirmwareError("No se encontró el Intel HEX característico del actualizador")
    if executable.find(_UPDATER_MARKER, start + 1) >= 0:
        raise FirmwareError("Hay varias cadenas candidatas; se requiere revisión manual")
    end = start
    while end + 1 < len(executable) and executable[end] in _HEX_ALPHABET and executable[end + 1] == 0:
        end += 2
    try:
        text = executable[start:end:2].decode("ascii")
    except UnicodeDecodeError as exc:
        raise FirmwareError("La cadena integrada no es ASCII") from exc
    image, records = decode_intel_hex(text)
    return image, text, records


def inspect_image(image: bytes, *, base: int = FLASH_BASE, records: int | None = None) -> ImageInfo:
    if len(image) != FLASH_SIZE:
        raise FirmwareError(f"Tamaño incorrecto: {len(image)}; se esperaban {FLASH_SIZE} bytes")
    initial_sp, reset_vector = struct.unpack_from("<II", image)
    if not 0x20000000 <= initial_sp < 0x20040000:
        raise FirmwareError(f"Stack pointer inicial no plausible: 0x{initial_sp:08X}")
    if reset_vector & 1 == 0 or not base <= (reset_vector & ~1) < base + len(image):
        raise FirmwareError(f"Vector reset Thumb no plausible: 0x{reset_vector:08X}")
    return ImageInfo(base, len(image), sha256(image).hexdigest(), initial_sp, reset_vector, records)


def encode_intel_hex(image: bytes, *, base: int = FLASH_BASE) -> str:
    """Genera Intel HEX con registros de 16 bytes y checksums correctos."""
    lines: list[str] = []
    current_upper: int | None = None

    def line(address: int, kind: int, data: bytes) -> str:
        body = bytes([len(data)]) + address.to_bytes(2, "big") + bytes([kind]) + data
        checksum = (-sum(body)) & 0xFF
        return ":" + (body + bytes([checksum])).hex().upper()

    for offset in range(0, len(image), 16):
        absolute = base + offset
        upper = absolute >> 16
        if upper != current_upper:
            lines.append(line(0, 4, upper.to_bytes(2, "big")))
            current_upper = upper
        lines.append(line(absolute & 0xFFFF, 0, image[offset:offset + 16]))
    lines.append(":00000001FF")
    return "\n".join(lines) + "\n"
