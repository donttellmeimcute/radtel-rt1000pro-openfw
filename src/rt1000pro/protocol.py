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
CONNECT_DELAY = 0.050
UPDATE_DELAY = 0.010
BLOCK_DELAY = 0.010


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
    """Flashea una imagen validada, sin reintentos automáticos."""
    inspect_image(image)
    dry_run(image)
    if not 0.5 <= timeout <= 30.0:
        raise FirmwareError("El timeout debe estar entre 0,5 y 30 segundos")
    try:
        import serial
    except ImportError as exc:
        raise FirmwareError("Falta pyserial; instala el extra 'serial'") from exc

    def write_all(ser, data: bytes, stage: str) -> None:
        written = ser.write(data)
        if written != len(data):
            raise FirmwareError(f"Escritura parcial en {stage}: {written}/{len(data)} bytes")
        ser.flush()

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
            # Secuencia y pausas conservadoras del programa original; sin reintentos.
            for attempt in range(1, 4):
                write_all(ser, CONNECT, f"CONNECT {attempt}/3")
                wait_ack(ser, f"CONNECT {attempt}/3")
                if attempt < 3:
                    time.sleep(CONNECT_DELAY)
            write_all(ser, UPDATE, "UPDATE")
            wait_ack(ser, "UPDATE")
            time.sleep(UPDATE_DELAY)
            for index, offset in enumerate(range(0, len(image), BLOCK_SIZE), 1):
                write_all(ser, build_data_packet(image, offset), f"bloque {index}/{BLOCK_COUNT}")
                wait_ack(ser, f"bloque {index}/{BLOCK_COUNT}")
                if progress:
                    progress(index, BLOCK_COUNT)
                if index < BLOCK_COUNT:
                    time.sleep(BLOCK_DELAY)
    except FirmwareError:
        raise
    except (OSError, serial.SerialException) as exc:
        raise FirmwareError(f"Error de puerto serie: {exc}") from exc
    return FlashResult(BLOCK_COUNT, len(image), False)
