# Regresión de los Fields de una nueva revisión

Esta prueba requiere compilar el conector corregido con autorización. No se considera cubierta por las pruebas Python de validación del formulario. Trabajar exclusivamente con copias temporales y una instancia CAD independiente.

1. Preparar una copia de una viñeta dinámica compatible: una tabla de seis columnas y cuatro Fields `CustomDP` en la primera fila (`Revision`, `Fecha_Rev`, `Dibujante`, `Comentario-rev`). El padre debe tener evaluación automática, valor 63. Conservar un respaldo de la copia y un inventario de viewports antes del ensayo.
2. Usar **Nueva revisión** para crear una revisión de prueba, por ejemplo `Z`. No ejecutar un reparador de Fields: el ensayo debe comprobar lo que produjo el conector por sí solo.
3. Abrir el resultado en ZWCAD y cargar `revision_fields_regression.lsp`. Obtener el handle de la tabla de revisiones y ejecutar `(SRFT:Check "HANDLE" "Z")`. Debe devolver `T`; comprueba que tanto el padre como sus hijos conservan 63.
4. En DWGPROPS cambiar `Revision` a `Y`, cambiar `Fecha_Rev` y aceptar. Ejecutar solamente `REGENALL`. El resultado debe mostrar `Y` y la fecha nueva. Repetir `(SRFT:Check "HANDLE" "Y")`.
5. Guardar, cerrar y abrir nuevamente la copia. Repetir la comprobación. Cambiar otra vez DWGPROPS y repetir `REGENALL` para descartar que se esté leyendo sólo el resultado guardado.
6. Comparar todos los viewports con el inventario inicial: centros, tamaños, escala, dirección, destino, giro, recortes, bloqueo y capas congeladas deben conservarse. Las filas históricas, dimensiones de la tabla y códigos de los Fields tampoco deben cambiar en los pasos 4 y 5.
7. Repetir el recorrido en AutoCAD y para las versiones de conector soportadas. Las pruebas `tests/test_revisions.py` con `SINCAL_TEST_REVISION_DWG` verifican además desplazamiento del historial, campos, geometría, respaldos y rechazo de revisiones repetidas sobre copias temporales.

La regresión falla con un padre 63 y un hijo 0 aunque el texto inicial sea correcto: evaluar con `Preview` fuerza un resultado, pero no comprueba que el Field vaya a responder a cambios futuros de DWGPROPS.

## Reparación de cuadros existentes

El conector acepta `revisionFieldRepairTables: ["HANDLE"]` como operación de
mantenimiento independiente. No se puede mezclar con lectura/edición de
revisiones o cambios de propiedades. La selección es explícita y se limita a
tablas de viñeta compatibles. El resto de las tablas se inspecciona únicamente
para comprobar que sus Fields no cambien por una referencia compartida.

El resultado se verifica antes y después del guardado: propiedades, versión DWG,
historial, formato de celdas, dimensiones, inventario de entidades y viewports.
Los únicos identificadores que pueden reconstruirse son los de los cuatro Fields
actuales de una tabla reparada; sus expresiones deben mantenerse. Esto es
necesario porque cambiar solamente las opciones del Field expuesto, incluso
mediante la API nativa, se pierde cuando la tabla vuelve a guardar su árbol.

Para ejecutar la regresión nativa con copias, definir `SINCAL_TEST_FIELD_DWG` y
`SINCAL_TEST_FIELD_TABLE`, y ejecutar `pytest tests/test_revision_fields.py`.
Opcionalmente `SINCAL_TEST_CONNECTOR_ROOT` apunta a una carpeta aislada con
`bin2025/Sincal.DwgProps.dll` y `bin2027/Sincal.DwgProps.dll`. La prueba comprueba
que un identificador inválido no reemplaza la copia y que el original conserva
su hash. Las pruebas sin estas variables no inician CAD.

Completar siempre la prueba guardando/reabriendo en ZWCAD y cambiando nuevamente
DWGPROPS mediante `REGENALL`, sin volver a ejecutar ningún reparador ni forzar
`Preview`. Registrar el texto leído directamente de la tabla: una respuesta del
editor que sustituya el texto por SummaryInfo no demuestra que el FIELD funcione.

## Validación realizada el 9 de noviembre de 2026

- Conectores AutoCAD 2025 y 2027 compilados sin errores; creación de revisión
  nueva y reparación del cuadro existente verificadas sobre copias.
- ZWCAD 2026: cambio de propiedad H → I, guardado, cierre, reapertura y nuevo
  cambio I → J mediante `REGENALL`, sin ejecutar un reparador entre cambios.
  Lectura directa de la tabla correcta, Fields automáticos y comprobaciones de
  historial, geometría y viewports aprobadas en ambos pasos.
- Se probó también la copia generada por Nueva revisión: Z → I, guardado y
  reapertura, I → J. Los campos respondieron a ambos cambios.
- Los originales no se reemplazaron y no se modificó la instalación de CAD.
