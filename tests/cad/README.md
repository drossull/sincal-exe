# Pruebas nativas de TXT-JOIN

Ejecutar **solamente en un dibujo desechable**. Antes de iniciar AcCoreConsole, establecer la variable de entorno `SINCAL_TEST_ROOT` a la ruta absoluta del repositorio (en PowerShell desde la raíz: `$env:SINCAL_TEST_ROOT = (Get-Location).Path`). Para ejecutar desde AutoCAD abierto, usar `(setenv "SINCAL_TEST_ROOT" "C:/ruta/sincal-exe")`. Las pruebas crean textos, MTEXT y una capa bloqueada; modifican PICKFIRST, CMDECHO, OSMODE y UNDO Auto en esa sesión.

`txt_join_regression.lsp` se carga después de `lisps/TXT-JOIN.lsp` y ejecuta 24 comprobaciones sobre las funciones reales de AutoLISP: caracteres y símbolos, espacios, orden geométrico, tolerancias, texto girado y justificado, duplicados, exclusiones y almacenamiento de MTEXT largo.

`txt_join_structured.lsp` se carga después de la regresión y comprueba párrafos continuos, jerarquías opcionales y existentes, exponentes, listas de campos, tabulaciones y almacenamiento nativo del MTEXT con ancho definido.

`txt_join_workflow.scr` carga los tres LISP y añade comprobaciones interactivas automatizadas: Cancelar, Conservar, Reemplazar seguido de un Deshacer, capas bloqueadas y modo Párrafos con ancho y sangría. Usar SCRIPT o el parámetro `/s` de AcCoreConsole. Debe imprimir `TXT-JOIN_TEST_FAILURES=0`, `TXT-JOIN_STRUCTURED_FAILURES=0` y `TXT-JOIN_WORKFLOW_FAILURES=0`.

El script elimina reactores de la sesión de prueba y desactiva UNDO Auto durante las pruebas de interacción para evitar que AutoCAD agrupe el script completo como una sola operación. Reactiva UNDO Auto al terminar. Ejecutar en una sesión aislada, nunca en la sesión de trabajo. El comando TXT-JOIN no elimina reactores y mantiene su propio grupo Begin/End.

Estas pruebas no certifican la reconstrucción de cualquier plano: se debe revisar el resultado con un DWG representativo, especialmente separaciones ambiguas, fuentes mixtas y tablas. No implementa OCR de geometría.

## Lanzadores CMD

`cmd_scripts_smoke.ps1` ejecuta los siete `.bat` reales usando Windows PowerShell
5.1, rutas con espacios y una copia de una plantilla vacía. Crea un directorio
temporal único y conserva allí los dibujos y registros; no usa planos de trabajo.
Recibe `-EnginePath` (accoreconsole.exe) y `-TemplatePath` (por ejemplo acadiso.dwt).

Comprueba por reapertura del DWG: geometría conservada, escalas sin uso eliminadas
por PURGEALL y escala actual conservada, bloqueo de ventanas por BV, eliminación
de Layout2 por DL2, dispositivo/papel A1 y existencia de PDF. La ejecución termina
con error si falla algún caso: salir con código cero no demuestra por sí solo que
el script haya aplicado sus cambios.

Revisión del 30-09-2026 en AutoCAD Core Console 2025:

- PURGEALL, AUDIT, BV, DL2 y ZE: comprobaciones correctas.
- PAGESETUP-A1: conserva `none_device` y papel A4 en la plantilla de prueba; no
  aplica la configuración anunciada. Pendiente de corrección específica.
- PUBLISH-A1: no genera PDF desde esa plantilla sin dispositivo configurado;
  el lanzador detecta y comunica el fallo. Pendiente de corrección específica.
- ZWCAD: no ejecutado en esta revisión.

La corrección de PURGEALL separa las respuestas de SCALELISTEDIT mediante saltos
de línea. El controlador compartido utiliza `System.Diagnostics.Process` para
evitar el `ExitCode` nulo que se reprodujo con `Start-Process -NoNewWindow` en
Windows PowerShell 5.1.
