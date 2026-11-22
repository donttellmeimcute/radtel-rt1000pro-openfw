# Ingeniería inversa del paquete 260611

## 1. Cadena de análisis

El ZIP analizado contiene únicamente `Radtel_RT-1000Pro_Update 260611.exe`, un ejecutable PE32 para Windows compilado como ensamblado .NET. No se ejecutó durante el análisis.

La lógica del formulario `Ido_Update.UpDate` contiene una cadena `allcode` con Intel HEX concatenado. En el `.exe`, esa cadena está almacenada en UTF-16LE y comienza por `:020000040800F2`. El extractor del repositorio localiza ese marcador y decodifica directamente los caracteres hasta el final de la cadena.

Resultados de la extracción:

- 15.242 registros Intel HEX válidos, incluido EOF.
- Arquitectura: ARM Thumb, según vectores e instrucciones.
- Dirección de carga: `0x08002800`.
- Tamaño transmitido: 251.904 bytes, 246 KiB.
- SP inicial: `0x2000AEC8`.
- Vector de reset: `0x08002AC1`.
- Relleno del actualizador hasta el tamaño completo: `0x00`.
- SHA-256 de la imagen plana: `53005e01c88180bcec5d2c6e2d928a8464140f660e93cc66c6efcd2157827e32`.

La imagen contiene aplicación, no un volcado integral del dispositivo. El área anterior a `0x08002800` y otras memorias no están incluidas.

## 2. Protocolo de actualización

Parámetros recuperados del código serie:

- 115200 baudios, 8N1.
- DTR activo al seleccionar el puerto.
- Respuesta afirmativa de un byte: `0x06`.
- Respuesta de error: `0xFF`.

Comandos de cinco bytes:

| Función | Bytes |
|---|---|
| CONNECT | `39 33 05 10 28` |
| UPDATE | `39 33 05 55 6D` |
| END, presente pero no usado en el flujo principal | `39 33 05 EE 06` |

El flujo original envía CONNECT tres veces, esperando `0x06` después de cada uno. Después envía UPDATE y espera otro `0x06`.

Cada trama de datos tiene 1.028 bytes:

| Campo | Tamaño | Descripción |
|---|---:|---|
| Marca | 1 | Siempre `0x57` |
| Offset | 2 | Offset del bloque dentro de la imagen, big-endian |
| Payload | 1024 | Datos consecutivos de firmware |
| Checksum | 1 | Suma modular descrita abajo |

Para los primeros 1.027 bytes de la trama:

```text
checksum = (sum(trama[0:1027]) + 0x52 + 0x54 + 1) mod 256
```

El emisor original incrementa el offset en 1024 y espera un ACK antes de continuar. El último offset es `0x3D000`. El código original cierra tras emitir el último bloque; esta implementación espera también su ACK para detectar rechazos.

## 3. Cadenas y funciones relevantes

La imagen conserva numerosas cadenas de interfaz. Entre ellas:

- `ALL BAND`, `64-999MHz`, `18-64MHz`.
- `All Band Test Mode`.
- `Air TX On-off`.
- `RX/TX Limit`, `Prohibit TX`.
- `Password`.

Las referencias se localizaron mediante instrucciones Thumb `ADR` y tablas de literales, no únicamente mediante coincidencias de texto.

### 3.1 Activación de ALL BAND

En `0x080035B4` hay una rutina de arranque que obtiene una tecla mediante `0x08013D94`. Si el resultado es `0x0E`, escribe `1` en la variable RAM `0x200010DA`.

```text
080035E6  cmp r4, #0x0E
080035E8  bne 0x080035F0     ; bytes 02 D1
080035EA  movs r0, #1
080035EC  ldr r1, =0x200010DA
080035EE  strb r0, [r1]
```

El parche sustituye `BNE` por `NOP` (`00 BF`), de modo que la escritura existente se ejecuta en cada arranque. No se añade código nuevo ni se desplaza ninguna dirección.

### 3.2 Comparación del diálogo restringido

La función de `0x08007FD4` gestiona un diálogo titulado `Password`. En `0x080080AC` llama a una comparación de 16 bytes situada en `0x08008270`. Esa función devuelve `1` si los buffers son iguales y `0` en caso contrario.

```text
080080B2  bl 0x08008270
080080B6  cmp r0, #0
080080B8  beq 0x08008014     ; bytes AC D0: vuelve a pedir si difiere
080080BA  pop ... pc         ; continúa si coincide
```

El parche sustituye `BEQ` por `NOP`, por lo que el diálogo continúa independientemente del resultado. No revela ni almacena una contraseña y no modifica las rutinas de RF.

### 3.3 Restricciones no modificadas

Las cadenas `Prohibit TX` tienen varias rutinas asociadas y distintas causas de bloqueo. No se ha generalizado un bypass para ellas. Tampoco se han cambiado límites numéricos de frecuencia, potencia, calibración o tablas de banda. El comportamiento de RF de la variante sigue requiriendo validación en hardware y uso legal.

## 4. Reproducibilidad

El perfil aplica dos sustituciones de dos bytes, sin cambiar el tamaño:

| Dirección | Original | Modificado | Finalidad |
|---|---|---|---|
| `0x080035E8` | `02 D1` | `00 BF` | ALL BAND en cada arranque |
| `0x080080B8` | `AC D0` | `00 BF` | Continuar tras el diálogo restringido |

La imagen `open-rx` resultante tiene SHA-256 `7f98fe67741f025c31718c804d6a7f112fa34a5b7d97fc7ddc3da0666397fcd4`.

Estas direcciones son específicas de 260611. No deben reutilizarse en otra compilación.
