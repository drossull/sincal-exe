# Pruebas de MARCAS-SC

Ejecutar en AutoCAD completo para Windows, en un documento desechable. Estas
pruebas usan ActiveX: AcCoreConsole no expone el documento COM necesario.
No ejecutar sobre un plano de producción. No requieren editar el master DWG.

1. Cargar `lisps/MARCAS-SC.lsp`.
2. Cargar `tests/cad/marcas_sc_regression.lsp`.
3. Confirmar `MARCAS_SC_TEST_FAILURES=0`.
4. Para probar UNDO/cancelación, establecer `SINCAL_TEST_ROOT` al repositorio y
   ejecutar `SCRIPT` con `tests/cad/marcas_sc_workflow.scr` en ese dibujo.
5. Confirmar `MARCAS_SC_UNDO_FAILURES=0`. Cerrar sin guardar.

La regresión crea una tabla y rótulos, verifica campos reales y sus evaluaciones,
edita diámetro, renumera, inserta/elimina filas, detecta duplicados, modifica un
atributo manualmente y elimina la tabla. No es una simulación de AutoLISP.

## Plantilla dinámica V2

`MARCA-SC`, Enter en la selección del modelo, importa
`masters/SINCAL_MARCA_SC_V2.dwg`. Define altura en papel (2.5 por defecto).
La plantilla usa RomanD del plano de referencia, círculo ACI 1, flip lateral y
estados SIN_CANTIDAD / CON_CANTIDAD. Ambos atributos de descripción son MText
con máscara de fondo, DXF 90=3 y margen DXF 45=1.2. XX es el número editable;
MARCA y MARCA_CANT contienen campos nativos administrados.

El importador establece explícitamente AcadAnnotative en la definición antes
de insertar referencias, porque la exportación/importación de la definición
dinámica no siempre conserva ese dato. OBJECTSCALE permite añadir escalas.
Seleccionar un modelo antiguo copia ese modelo; no lo convierte a la plantilla.

Ejecutar `python tools/cad/test_marcas_native.py` en Windows con AutoCAD 2025 y
pywin32. Crea una instancia separada y cierra sin guardar; `--keep-open` deja
el dibujo desechable para inspección. La prueba usa el portapapeles para probar
COPYBASE/PASTECLIP (reemplaza su contenido). Confirma `DONE failures=0`.
Comprueba campos, máscaras, RomanD, color, propiedades dinámicas, copia y edición
automática, marca inexistente y escalas 1:1 / 1:2. No usa el dibujo del usuario.

Para regenerar la geometría, cargar `tools/cad/build_marca_sc.lsp` en una COPIA
desechable que tenga RomanD y ejecutar `(SCMB:Build)`. Exportar exclusivamente
SINCAL_MARCA_SC_V2 mediante -WBLOCK. No guardar el plano fuente.

Revisión visual: probar las cuatro combinaciones de flip/visibilidad; poner una
línea detrás del texto para comprobar la máscara; comprobar lectura normal a
ambos lados. Cambiar la escala con las representaciones añadidas al bloque.

Los datos de identidad se guardan en CustomData de la celda A y XData del bloque.
Mover una fila completa debe conservar sus metadatos; pegar solamente valores
no constituye una migración de identidad. Las referencias nativas se reparan al
ejecutar ACTUALIZAR-MARCAS. Los reactores reparan campos al finalizar comandos
o evaluaciones LISP; la notificación de objeto únicamente marca trabajo pendiente.
Se requiere cargar MARCAS-SC.lsp en cada documento. Para herramientas que no
finalicen un comando, REGEN procesa los cambios. No se escribe en callbacks de
modificación, ni se usan comandos interactivos en callbacks. UNDO/REDO no dispara
una reparación que anule la operación del usuario. Capas bloqueadas se omiten.

Al editar XX se busca una marca única en la tabla registrada. Si no existe, se
borra la descripción anterior y se muestra [SIN VINCULO]. Copiar a otro dibujo
sin la tabla no autoriza a elegir otra por coincidencia: usar REASIGNAR-MARCA.
El XRecord SINCAL_MARCA_DOCUMENT_V1 identifica el dibujo. El bloque conserva un
respaldo de su handle de tabla y de esa identidad: permite recuperar COPYCLIP
cuando AutoCAD sustituye por cero un handle 1005 no incluido en la selección.
Ese respaldo no se utiliza si la identidad del documento no coincide.
Solo se admiten marcas numéricas, cantidad entera positiva y diámetro/separación
positivos; el sistema no calcula cantidades a partir del número de rótulos.
