# rt1000pro-openfw

Herramientas abiertas de ingeniería inversa, extracción, parcheo y actualización para el firmware **Radtel RT-1000Pro 260611**.

> **Estado: experimental, sin pruebas en hardware.** Este repositorio no es todavía una reimplementación limpia y completa del firmware. La versión `open-rx` aplica dos cambios mínimos sobre una copia del firmware que ya poseas. No se distribuyen el actualizador ni imágenes propietarias.

## Qué incluye

- Extractor estático del Intel HEX incrustado en el `.exe` .NET; no ejecuta el actualizador.
- Validación de registros, checksums, direcciones, tamaño y vectores ARM Thumb.
- Perfil `open-rx` bloqueado al hash exacto de la versión compatible.
- Generador y simulador de las 246 tramas de actualización.
- Flasheador serie opcional con confirmaciones explícitas.
- Pruebas automáticas y notas de ingeniería inversa.

## Alcance del perfil `open-rx`

1. **ALL BAND al arrancar:** activa el modo de banda completa ya presente en el firmware.
2. **Acceso a menús restringidos:** omite el resultado de la comparación de contraseña en el diálogo común de acceso.

No se modifican directamente las tablas de frecuencias, la potencia, la función `Prohibit TX` ni otras comprobaciones de RF. El efecto completo del modo ALL BAND sobre el hardware todavía no está validado. **No transmitas fuera de las bandas, modos o potencias permitidos en tu jurisdicción y licencia.**

## Compatibilidad y hashes

Solo se admite la imagen de 246 KiB extraída del paquete `Radtel_RT-1000Pro_Update 260611.exe` analizado:

| Imagen | SHA-256 |
|---|---|
| Original 260611 | `53005e01c88180bcec5d2c6e2d928a8464140f660e93cc66c6efcd2157827e32` |
| `open-rx` | `7f98fe67741f025c31718c804d6a7f112fa34a5b7d97fc7ddc3da0666397fcd4` |

No uses el parche con otra versión ni con otro modelo. La comprobación de hash y de los bytes originales lo impedirá por defecto.

## Instalación

Requiere Python 3.10 o posterior. Las funciones de extracción, parcheo y simulación no tienen dependencias externas.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install -e '.[dev]'
pytest -q
```

Para el flasheo serie se instala `pyserial` mediante el extra `serial`, ya incluido en `dev`.

## Generar la variante localmente

```bash
rt1000pro extract "Radtel_RT-1000Pro_Update 260611.exe" \
  -o rt1000pro-260611-stock.bin \
  --hex-output rt1000pro-260611-stock.hex

rt1000pro info rt1000pro-260611-stock.bin

rt1000pro patch rt1000pro-260611-stock.bin \
  -o rt1000pro-260611-open-rx.bin \
  --manifest open-rx-manifest.json

rt1000pro simulate rt1000pro-260611-open-rx.bin
```

Los archivos `.exe`, `.zip`, `.bin` y `.hex` están excluidos por `.gitignore` para evitar publicar accidentalmente material propietario.

## Flasheo

**No recomiendo flashear esta primera variante hasta disponer de una copia integral de recuperación y validación independiente en hardware.** Una interrupción o una imagen incompatible puede dejar la radio inutilizable.

El programa original indica este procedimiento de bootloader: conectar el cable, mantener PTT al encender y después iniciar la actualización. El puerto trabaja a 115200 baudios, 8N1, con DTR activo.

```bash
rt1000pro simulate rt1000pro-260611-open-rx.bin
rt1000pro flash rt1000pro-260611-open-rx.bin \
  --port /dev/ttyUSB0 \
  --confirm-model RT-1000PRO --yes
```

En Windows, sustituye el puerto por ejemplo por `COM4`. El flasheador solo acepta los dos hashes conocidos indicados arriba. Consulta [seguridad y flasheo](docs/seguridad-y-flasheo.md) antes de usarlo.

## Documentación

- [Ingeniería inversa y formato](docs/ingenieria-inversa.md)
- [Seguridad, límites y flasheo](docs/seguridad-y-flasheo.md)

## Licencia

El código, la documentación y las descripciones de parches originales de este repositorio se publican bajo Apache-2.0. Esta licencia **no** se aplica al firmware ni al actualizador propietario del fabricante, que no se redistribuyen aquí. Radtel es una marca de su respectivo titular; este proyecto no está afiliado al fabricante.
