# Seguridad, límites y flasheo

## Estado de validación

La versión `open-rx` se ha validado únicamente mediante:

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

## Límites deliberados del proyecto

- No se publica el `.exe`, el ZIP ni imágenes propietarias.
- No se afirma que el firmware sea una reimplementación open source completa.
- No se eliminan de forma generalizada `Prohibit TX`, límites de potencia o validaciones de frecuencia.
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
