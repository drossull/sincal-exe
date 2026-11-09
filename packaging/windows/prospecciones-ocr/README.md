# Motor OCR de Prospecciones

El motor PaddleOCR se instala y actualiza independientemente de SINCAL. La
pantalla de Prospecciones, sus tablas, sesiones e inserciones CAD permanecen
en el programa principal. La lectura de TXT y PDF con texto no requiere este
complemento; los informes que necesitan reconocimiento de imágenes sí.

## Construcción independiente

Con CPython 3.12 x64 e Inno Setup:

```powershell
python tools/build_ocr_module.py
```

Primero prepara `ocr_runtime/` con los modelos y dependencias fijados del
proyecto. `--skip-runtime` usa esa carpeta existente, verificando el lock, el
worker y los modelos antes de empaquetar. `--skip-installer` produce sólo ZIP.
`--iscc RUTA` permite seleccionar Inno Setup y `--output-dir RUTA` el destino.
`--force` reempaqueta aunque las huellas coincidan.

La salida en `installer_output/prospecciones-ocr/v1.0.0/` contiene:

- `Setup_SINCAL_OCR_v1.0.0.exe`, instalador posterior sin acceso directo propio.
- `SINCAL_OCR_v1.0.0.zip`, motor, licencias y manifiesto con hashes por archivo.
- `ocr-module-build.json`, versión independiente, rutas y SHA-256 del ZIP.
- `build-receipt.json`, comprobante local de entradas y salidas para reutilización.

No compila SINCAL, Pasarela ni los complementos CAD. No instala ni publica nada.
El instalador local se genera sin firma, igual que el empaquetado independiente
de Pasarela: debe firmarse y verificarse antes de publicarlo. Los registros,
comprobantes y `module-stage/` son salidas internas, no archivos para distribuir.
Si se firma el instalador después de construir, el comprobante se invalidará
en la siguiente ejecución; no debe reutilizarse un hash anterior a la firma.

## Instalación y compatibilidad

Ejecutar el instalador instala únicamente en
`%LOCALAPPDATA%/SINCAL/modules/prospecciones-ocr`. La actualización de ese
complemento retira sus dependencias antiguas y conserva proyectos y cachés de
trabajo, que están fuera del módulo. No modifica la instalación principal.

SINCAL busca primero el complemento por usuario, luego un complemento colocado
en `{app}/modules/prospecciones-ocr`, y finalmente el OCR anterior de
`{app}/ocr_runtime`. El instalador principal conserva esta última carpeta al
actualizar, de modo que los usuarios actuales no deben descargar de nuevo el
motor para recibir cambios en Armaduras. Una instalación nueva que no tenga
motor muestra un mensaje solicitando sólo este complemento al necesitar OCR.
Un módulo presente pero incompatible o incompleto pide reparación, sin
cambiar silenciosamente a otro motor.

Contrato: `schema: 1`, `id: prospecciones-ocr`, `worker_api: 1`,
`python_abi: 3.12`. Su versión se mantiene en `module.json`, independiente de
la versión de SINCAL. Al cambiar dependencias, modelos o protocolo, preparar
una versión nueva del complemento. El programa no descarga dependencias al
leer un informe ni importa Paddle en su proceso principal.
