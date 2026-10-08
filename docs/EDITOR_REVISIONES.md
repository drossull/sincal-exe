# Editor de revisiones

## Selección y datos comunes

- La lista tiene una casilla por DWG, buscador y selección de archivos visibles.
- La tabla común permite editar todas las filas de los archivos marcados, incluido el historial. Los valores distintos permanecen intactos hasta escribir un reemplazo.
- Para unificar todo el contenido, elige una tabla base y pulsa «Aplicar tabla base a seleccionados». Se incluyen sus cambios pendientes. La confirmación prepara borradores; no guarda archivos todavía.
- Se conservan los Fields y el formato de destino: se trasladan valores, no objetos de tabla. Si difieren las dimensiones de las tablas, un campo protegido tiene otro valor o una propiedad vinculada recibiría valores incompatibles, se rechaza la copia completa sin preparar cambios parciales.
- «Ver / editar» permite ajustar un archivo individual (por ejemplo, su dibujante) y revisar su historial.
- Desmarcar un archivo no borra su borrador. El resumen y la confirmación de guardado incluyen todos los cambios pendientes.
- Las etiquetas de Fields se muestran debajo de cada campo, sin superponerse con los valores.

En **Revisiones → Editor de revisiones**, selecciona archivos DWG o una carpeta
(se leen sus DWG directos, sin recorrer subcarpetas). Los archivos permanecen locales.
Elige un archivo de la lista para ver y editar su tabla. Puedes cambiar de archivo
sin perder los cambios pendientes. Revisa el resumen antes de guardar.

- Solo se reconocen tablas de revisiones dentro de bloques cuyo nombre efectivo
  empieza por `VIÑETA`, incluidos bloques dinámicos y viñetas anidadas.
- La compatibilidad inicial es el cuadro de Barrancón: seis columnas y un Field
  `CustomDP.Revision` en la primera celda. Las tablas de firmas no se confunden
  con las de revisiones. Una estructura no compatible se informa sin modificarla.
- Los Fields de la primera fila se conservan con su identidad, expresión y
  opciones de evaluación. Las celdas vinculadas compatibles se editan a través
  de sus propiedades personalizadas DWGPROPS; un Field no compatible es de solo lectura.
- Las propiedades son globales al DWG: otros textos vinculados pueden reflejar
  el nuevo valor. Se muestran las instancias que comparten una tabla.
- Las celdas de texto del historial se editan directamente. No se agregan ni
  desplazan filas; **Nueva revisión** permanece como herramienta independiente.
- Antes de reemplazar cada original, se guarda y reabre una copia y se comprueban
  Fields, contenido, dimensiones/formato comprobado, estructura y viewports.
  El archivo previo se respalda en `SINCAL_Backups/<operación>/`.
- Cierra los DWG en CAD antes de guardar. Si un archivo cambió después de la
  lectura, hay que volver a cargarlo. Textos que cambien las dimensiones de la
  tabla se rechazan. No se admiten códigos de formato ni Fields nuevos.
- El guardado es por archivo: un error o cancelación no revierte los DWG ya
  guardados. Los resultados indican cuáles se guardaron y dónde está el respaldo;
  las ediciones no guardadas permanecen pendientes.

Requiere un motor AutoCAD Core Console con conector compatible (2025/2027).
Esta herramienta no depende de una sesión CAD interactiva.

## Verificación

`tests/test_revision_editor.py` valida cambios, autorización de rutas y guardado.
Con `SINCAL_TEST_EDITOR_FOLDER` apuntando a NATIVOS de Barrancón, ejecuta la prueba
nativa en **copias temporales** de DD-01 y PG-01 para ambos motores. Comprueba
Fields, historial, respaldo, reapertura y rechazo de una lectura desactualizada.
`tests/selfcheck_revision_editor_ui.cjs` comprueba el flujo visual con API simulada,
sin abrir ni escribir planos del usuario.
