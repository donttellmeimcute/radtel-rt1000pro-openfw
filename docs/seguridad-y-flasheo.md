# Seguridad, límites y flasheo

## Estado de validación

Las variantes `open-rx`, `airband-tx` y `open-rx-airband-tx` se han validado únicamente mediante:

- extracción reproducible del paquete original;
- comprobación de todos los checksums Intel HEX;
- verificación de vectores ARM Thumb y tamaño;
- comprobación de los bytes antes y después de cada parche;
- pruebas automáticas del formato y checksum de las 246 tramas serie.

**No se ha flasheado ni ejecutado en una RT-1000Pro física.** No hay garantía de funcionamiento, recuperación, recepción, transmisión o seguridad del hardware.

## Antes de considerar un flasheo

1. Confirma que el modelo es exactamente RT-1000Pro y que la imagen de partida tiene el hash documentado.
2. Consigue un método independiente para hacer y restaurar una copia integral de la flash y de la calibración. La imagen del actualizador no es una copia integral.
3. Conserva el paquete original y anota los hashes.
4. No uses la radio como equipo de emergencia o comunicación crítica durante las pruebas.
5. Utiliza una carga fantasma y instrumentación adecuada para cualquier prueba de TX. No transmitas al aire fuera de tus permisos.
6. Ejecuta siempre `rt1000pro simulate` antes de abrir el puerto.

Si no dispones de recuperación, lo prudente es no flashear esta versión experimental.

## Procedimiento conservador incorporado

1. Para Airband, utiliza solamente `airband-tx`: dos bytes cambiados, sin acumular los parches de `open-rx`.
2. Ejecuta `rt1000pro preflight IMAGEN` y comprueba manualmente que el perfil y SHA-256 son los esperados.
3. El flasheo exige `--recovery-confirmed` y `--power-confirmed`, además del modelo y la aceptación del riesgo.
4. Airband exige también `--authorized-airband`.
5. Cada escritura debe completarse y recibir ACK; un envío parcial, respuesta inesperada o timeout detiene el proceso.
6. Se aplican pausas conservadoras equivalentes a las del actualizador original y no se reintenta automáticamente.
7. Se espera ACK incluso del último bloque. No existe lectura posterior de la flash: el ACK no demuestra que toda la ejecución sea correcta.

Las confirmaciones no son comprobaciones físicas. Si no has realizado realmente el respaldo y la restauración de prueba, no uses esas opciones.

## Riesgo específico de Airband

Los perfiles `airband-tx` y `open-rx-airband-tx` eliminan una comprobación de software asociada al modo aeronáutico. Esto no certifica que el equipo cumpla la normativa de emisión, estabilidad, espectro o modulación aeronáutica.

- No conectes una antena para las primeras pruebas: utiliza una carga fantasma adecuada y atenuación/instrumentación.
- No transmitas al aire sin una autorización explícita y vigente para esa banda y ese equipo.
- No uses la variante cerca de operaciones aeronáuticas, aeropuertos o sistemas de navegación.
- Restaura el firmware original si observas comportamiento inesperado.
- El flasheador exige `--authorized-airband` para estas imágenes; esa confirmación no sustituye ningún permiso legal.

## Límites deliberados del proyecto

- No se publica el `.exe`, el ZIP ni imágenes propietarias.
- No se afirma que el firmware sea una reimplementación open source completa.
- No se elimina de forma generalizada `Prohibit TX`; el cambio aeronáutico se limita al desvío documentado en `0x0800810E`.
- No se modifican potencia, calibración ni los límites inferiores de 108 MHz y superior de 136 MHz.
- No se acepta otra versión mediante los comandos normales de parcheo o flasheo.
- No se ejecuta el actualizador durante la extracción.

El usuario es responsable de cumplir la regulación y las condiciones de su licencia de radio. Las funciones de diagnóstico o banda completa no constituyen autorización para transmitir.

## Recuperación ante errores

Un error de comunicación no implica necesariamente que la imagen esté dañada, pero sí debes dejar de reintentar ciegamente:

1. No apagues si una escritura sigue activa.
2. Conserva el mensaje de error y el último bloque confirmado.
3. Comprueba cable, puerto y modo bootloader.
4. Vuelve a la imagen original solamente si tienes un procedimiento de recuperación conocido.

La herramienta no puede garantizar que el bootloader permanezca accesible después de una escritura incompleta.
