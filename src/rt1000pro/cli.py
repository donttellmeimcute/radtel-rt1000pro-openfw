"""Interfaz de línea de comandos del proyecto."""

from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
import sys

from . import STOCK_260611_SHA256
from .firmware import FirmwareError, decode_intel_hex, extract_updater, inspect_image
from .patches import PATCHED_SHA256, PROFILES, apply_profile, manifest
from .protocol import dry_run, flash

AIRBAND_PROFILES = frozenset(("airband-tx", "open-rx-airband-tx"))


def _read_image(path: str) -> bytes:
    data = Path(path).read_bytes()
    if path.lower().endswith((".hex", ".ihx")):
        image, _ = decode_intel_hex(data.decode("ascii"))
        return image
    return data


def _print_info(image: bytes, records: int | None = None) -> None:
    info = inspect_image(image, records=records)
    print(f"Base:          0x{info.base:08X}")
    print(f"Tamaño:        {info.size} bytes (246 bloques de 1 KiB)")
    print(f"SHA-256:       {info.sha256}")
    print(f"SP inicial:    0x{info.initial_sp:08X}")
    print(f"Reset Thumb:   0x{info.reset_vector:08X}")
    if info.records is not None:
        print(f"Registros HEX: {info.records}")


def _identify(image: bytes) -> tuple[str, str]:
    digest = sha256(image).hexdigest()
    if digest == STOCK_260611_SHA256:
        return digest, "stock-260611"
    for profile, known_digest in PATCHED_SHA256.items():
        if digest == known_digest:
            return digest, profile
    raise FirmwareError("Imagen desconocida; solo se admiten la versión 260611 y perfiles documentados")


def _preflight(image: bytes) -> tuple[str, str]:
    """Validación estática y de tramas; nunca abre el puerto serie."""
    digest, profile = _identify(image)
    result = dry_run(image)
    _print_info(image)
    print(f"Perfil:        {profile}")
    print(f"Simulación:    {result.blocks}/{result.blocks} tramas válidas")
    print(f"TX aeronáutica: {'SÍ' if profile in AIRBAND_PROFILES else 'no modificada'}")
    return digest, profile


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rt1000pro",
        description="Herramientas abiertas para el firmware Radtel RT-1000Pro 260611",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    extract = sub.add_parser("extract", help="Extrae la imagen del actualizador .NET, sin ejecutarlo")
    extract.add_argument("updater", help="Actualizador original .exe")
    extract.add_argument("-o", "--output", required=True, help="Imagen binaria de 246 KiB")
    extract.add_argument("--hex-output", help="También guarda el Intel HEX recuperado")

    info = sub.add_parser("info", help="Valida e identifica una imagen BIN o Intel HEX")
    info.add_argument("image")

    patch = sub.add_parser("patch", help="Aplica un perfil con comprobación de hash y bytes")
    patch.add_argument("image", help="Imagen original extraída")
    patch.add_argument("-o", "--output", required=True)
    patch.add_argument("--profile", choices=sorted(PROFILES), default="open-rx")
    patch.add_argument("--manifest", help="Guarda la descripción JSON de los cambios")

    simulate = sub.add_parser("simulate", help="Genera y valida las 246 tramas sin abrir el puerto")
    simulate.add_argument("image")

    preflight = sub.add_parser("preflight", help="Comprobación conservadora sin abrir el puerto serie")
    preflight.add_argument("image")

    flashing = sub.add_parser("flash", help="Flashea por serie; operación con riesgo de brick")
    flashing.add_argument("image")
    flashing.add_argument("--port", required=True, help="Por ejemplo COM4 o /dev/ttyUSB0")
    flashing.add_argument("--timeout", type=float, default=3.0)
    flashing.add_argument("--confirm-model", required=True, help="Debe ser exactamente RT-1000PRO")
    flashing.add_argument("--yes", action="store_true", help="Confirma que aceptas el riesgo de brick")
    flashing.add_argument(
        "--recovery-confirmed",
        action="store_true",
        help="Confirma respaldo integral y restauración externa ya comprobada",
    )
    flashing.add_argument(
        "--power-confirmed",
        action="store_true",
        help="Confirma batería, alimentación y cable estables",
    )
    flashing.add_argument(
        "--authorized-airband",
        action="store_true",
        help="Confirma autorización para TX aeronáutica; obligatorio con perfiles airband-tx",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "extract":
            image, hex_text, records = extract_updater(args.updater)
            Path(args.output).write_bytes(image)
            if args.hex_output:
                Path(args.hex_output).write_text(hex_text.replace(":", "\n:") + "\n", encoding="ascii")
            _print_info(image, records)
            print(f"Imagen guardada en: {args.output}")
        elif args.command == "info":
            _print_info(_read_image(args.image))
        elif args.command == "patch":
            result = apply_profile(_read_image(args.image), args.profile)
            Path(args.output).write_bytes(result)
            if args.manifest:
                Path(args.manifest).write_text(manifest(args.profile), encoding="utf-8")
            _print_info(result)
            print(f"Variante guardada en: {args.output}")
        elif args.command == "simulate":
            image = _read_image(args.image)
            result = dry_run(image)
            print(f"Simulación correcta: {result.blocks} bloques, {result.bytes_sent} bytes de payload")
            print(f"SHA-256: {sha256(image).hexdigest()}")
        elif args.command == "preflight":
            _, profile = _preflight(_read_image(args.image))
            print("\nAntes de flashear debes tener:")
            print("- respaldo integral de flash, bootloader, configuración y calibración;")
            print("- restauración externa ya probada, alimentación estable y cable verificado;")
            print("- una unidad de repuesto, no una radio usada para comunicaciones críticas.")
            if profile in AIRBAND_PROFILES:
                print("- autorización aeronáutica y plan de pruebas con carga fantasma, sin antena.")
            print("\nLa comprobación ha pasado, pero NO demuestra que flashear sea seguro.")
        elif args.command == "flash":
            image = _read_image(args.image)
            _, profile = _preflight(image)
            if args.confirm_model != "RT-1000PRO" or not args.yes:
                raise FirmwareError("Faltan --confirm-model RT-1000PRO y/o --yes")
            if not args.recovery_confirmed:
                raise FirmwareError(
                    "Flasheo bloqueado: confirma respaldo y restauración externa con --recovery-confirmed"
                )
            if not args.power_confirmed:
                raise FirmwareError("Flasheo bloqueado: confirma alimentación y cable con --power-confirmed")
            if profile in AIRBAND_PROFILES and not args.authorized_airband:
                raise FirmwareError(
                    "Esta variante habilita TX aeronáutica: confirma tu autorización con --authorized-airband"
                )
            print("\nMantén PTT al encender para entrar en bootloader.")
            print("No hay lectura posterior ni reintentos automáticos. No interrumpas el proceso.")
            result = flash(
                image,
                args.port,
                timeout=args.timeout,
                progress=lambda done, total: print(f"\rBloques: {done}/{total}", end="", flush=True),
            )
            print(f"\nFlasheo completado con ACK en los {result.blocks} bloques")
            print("Antes de usar RF, reinicia y valida primero recepción, menús y recuperación.")
        return 0
    except (FirmwareError, OSError, UnicodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nOperación cancelada; no desconectes si había comenzado la escritura.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
