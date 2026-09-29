# Pruebas nativas de TXT-JOIN

Ejecutar **solamente en un dibujo desechable**. Antes de iniciar AcCoreConsole, establecer la variable de entorno `SINCAL_TEST_ROOT` a la ruta absoluta del repositorio (en PowerShell desde la raíz: `$env:SINCAL_TEST_ROOT = (Get-Location).Path`). Para ejecutar desde AutoCAD abierto, usar `(setenv "SINCAL_TEST_ROOT" "C:/ruta/sincal-exe")`. Las pruebas crean textos, MTEXT y una capa bloqueada; modifican PICKFIRST, CMDECHO, OSMODE y UNDO Auto en esa sesión.

`txt_join_regression.lsp` se carga después de `lisps/TXT-JOIN.lsp` y ejecuta 24 comprobaciones sobre las funciones reales de AutoLISP: caracteres y símbolos, espacios, orden geométrico, tolerancias, texto girado y justificado, duplicados, exclusiones y almacenamiento de MTEXT largo.

`txt_join_structured.lsp` se carga después de la regresión y comprueba párrafos continuos, jerarquías opcionales y existentes, exponentes, listas de campos, tabulaciones y almacenamiento nativo del MTEXT con ancho definido.

`txt_join_workflow.scr` carga los tres LISP y añade comprobaciones interactivas automatizadas: Cancelar, Conservar, Reemplazar seguido de un Deshacer, capas bloqueadas y modo Párrafos con ancho y sangría. Usar SCRIPT o el parámetro `/s` de AcCoreConsole. Debe imprimir `TXT-JOIN_TEST_FAILURES=0`, `TXT-JOIN_STRUCTURED_FAILURES=0` y `TXT-JOIN_WORKFLOW_FAILURES=0`.

El script elimina reactores de la sesión de prueba y desactiva UNDO Auto durante las pruebas de interacción para evitar que AutoCAD agrupe el script completo como una sola operación. Reactiva UNDO Auto al terminar. Ejecutar en una sesión aislada, nunca en la sesión de trabajo. El comando TXT-JOIN no elimina reactores y mantiene su propio grupo Begin/End.

Estas pruebas no certifican la reconstrucción de cualquier plano: se debe revisar el resultado con un DWG representativo, especialmente separaciones ambiguas, fuentes mixtas y tablas. No implementa OCR de geometría.
