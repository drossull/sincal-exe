# Pruebas nativas de TXT-JOIN

Ejecutar **solamente en un dibujo desechable**. Antes de iniciar AcCoreConsole, establecer la variable de entorno `SINCAL_TEST_ROOT` a la ruta absoluta del repositorio (en PowerShell desde la raíz: `$env:SINCAL_TEST_ROOT = (Get-Location).Path`). Para ejecutar desde AutoCAD abierto, usar `(setenv "SINCAL_TEST_ROOT" "C:/ruta/sincal-exe")`. Las pruebas crean textos, MTEXT y una capa bloqueada; modifican PICKFIRST, CMDECHO, OSMODE y UNDO Auto en esa sesión.

`txt_join_regression.lsp` se carga después de `lisps/TXT-JOIN.lsp` y ejecuta 24 comprobaciones sobre las funciones reales de AutoLISP: caracteres y símbolos, espacios, orden geométrico, tolerancias, texto girado y justificado, duplicados, exclusiones y almacenamiento de MTEXT largo.

`txt_join_workflow.scr` carga ambos LISP y añade cuatro comprobaciones interactivas automatizadas: Cancelar, Conservar, Reemplazar seguido de un Deshacer, y capas bloqueadas. Usar SCRIPT o el parámetro `/s` de AcCoreConsole. Debe imprimir `TXT-JOIN_TEST_FAILURES=0` y `TXT-JOIN_WORKFLOW_FAILURES=0`.

El script desactiva UNDO Auto durante las pruebas de interacción para evitar que AutoCAD agrupe el script completo como una sola operación. Lo reactiva al terminar. El comando TXT-JOIN mantiene su propio grupo Begin/End.

Estas pruebas no certifican la reconstrucción de cualquier plano: se debe revisar el resultado con un DWG representativo, especialmente separaciones ambiguas, fuentes mixtas y tablas. No implementa OCR de geometría.
