"""Protocolo serie 115200 8N1 recuperado estáticamente del actualizador."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Callable

from . import FLASH_SIZE
from .firmware import FirmwareError, inspect_image

CONNECT = bytes((0x39, 0x33, 0x05, 0x10, 0x28))
UPDATE = bytes((0x39, 0x33, 0x05, 0x55, 0x6D))
END = bytes((0x39, 0x33, 0x05, 0xEE, 0x06))
ACK = 0x06
ERROR = 0xFF
BLOCK_SIZE = 1024
BLOCK_COUNT = FLASH_SIZE // BLOCK_SIZE


def packet_checksum(packet_without_checksum: bytes) -> int:
    """Suma modular con la constante 'R' + 'T' + 1 del actualizador."""
    if len(packet_without_checksum) != 1027:
        raise ValueError("La entrada de checksum debe tener 1027 bytes")
    return (sum(packet_without_checksum) + 0x52 + 0x54 + 1) & 0xFF


def build_data_packet(image: bytes, offset: int) -> bytes:
    """Construye una trama de 1028 bytes: 0x57, offset BE, 1 KiB, checksum."""
    if offset < 0 or offset >= len(image) or offset % BLOCK_SIZE:
        raise ValueError(f"Offset inválido: {offset}")
    block = image[offset:offset + BLOCK_SIZE]
    if len(block) != BLOCK_SIZE:
        raise ValueError("Bloque incompleto")
    header = bytes((0x57, (offset >> 8) & 0xFF, offset & 0xFF))
    partial = header + block
    return partial + bytes((packet_checksum(partial),))


@dataclass(frozen=True)
class FlashResult:
    blocks: int
    bytes_sent: int
    simulated: bool


def dry_run(image: bytes) -> FlashResult:
    """Valida toda la secuencia sin abrir un puerto serie."""
    inspect_image(image)
    for offset in range(0, len(image), BLOCK_SIZE):
        packet = build_data_packet(image, offset)
        if len(packet) != 1028 or packet[-1] != packet_checksum(packet[:-1]):
            raise FirmwareError(f"Fallo interno validando el bloque {offset // BLOCK_SIZE}")
    return FlashResult(BLOCK_COUNT, len(image), True)


def flash(
    image: bytes,
    port: str,
    *,
    timeout: float = 3.0,
    progress: Callable[[int, int], None] | None = None,
) -> FlashResult:
    """Flashea una imagen validada. Requiere pyserial y modo bootloader."""
    inspect_image(image)
    dry_run(image)
    try:
        import serial
    except ImportError as exc:
        raise FirmwareError("Falta pyserial; instala el extra 'serial'") from exc

    def wait_ack(ser, stage: str) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = ser.read(1)
            if not value:
                continue
            if value[0] == ACK:
                return
            if value[0] == ERROR:
                raise FirmwareError(f"El bootloader rechazó {stage}")
            raise FirmwareError(f"Respuesta inesperada a {stage}: 0x{value[0]:02X}")
        raise FirmwareError(f"Tiempo de espera agotado esperando ACK de {stage}")

    try:
        with serial.Serial(
            port=port,
            baudrate=115200,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,
            write_timeout=timeout,
            dsrdtr=False,
            rtscts=False,
            xonxoff=False,
        ) as ser:
            ser.dtr = True
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            # El programa original emite CONNECT tres veces y espera ACK cada vez.
            for attempt in range(1, 4):
                ser.write(CONNECT)
                ser.flush()
                wait_ack(ser, f"CONNECT {attempt}/3")
            ser.write(UPDATE)
            ser.flush()
            wait_ack(ser, "UPDATE")
            for index, offset in enumerate(range(0, len(image), BLOCK_SIZE), 1):
                ser.write(build_data_packet(image, offset))
                ser.flush()
                wait_ack(ser, f"bloque {index}/{BLOCK_COUNT}")
                if progress:
                    progress(index, BLOCK_COUNT)
    except FirmwareError:
        raise
    except (OSError, serial.SerialException) as exc:
        raise FirmwareError(f"Error de puerto serie: {exc}") from exc
    return FlashResult(BLOCK_COUNT, len(image), False)
