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
Se admiten marcas formadas por dígitos y un sufijo opcional de letras A-Z:
`5`, `5a`, `5b`, `12AB`. Se conserva la escritura de la tabla, pero la búsqueda
y los duplicados no distinguen mayúsculas/minúsculas: `5a` y `5A` son la misma
marca. Se rechazan espacios internos, signos y fórmulas. La regresión verifica
renombrado, vinculación a una fila insertada, edición de XX y duplicados mixtos.
Se requiere cantidad entera positiva y diámetro/separación positivos; el sistema
no calcula cantidades a partir del número de rótulos. Los ID existentes no cambian.

Los campos de diámetro y separación muestran como máximo un decimal, sin ceros
finales (`7.500000` se muestra como `7.5`, `20` como `20`). La cantidad no muestra
decimales. Solo se redondea la presentación, sin modificar valores de la tabla.
ACTUALIZAR-MARCAS reconstruye también los campos antiguos sin este formato.

## MARCA-DE: despiece

`MARCA-DE` utiliza la variante `masters/SINCAL_MARCA_DE_V1.dwg`, derivada del
mismo diseño: círculo rojo, RomanD, máscara del diámetro y flip nativo, bloque anotativo.
Siempre muestra cantidad y largo (sin estados de visibilidad). Sus atributos
son XX (marca vinculada), MARCA (solo diámetro vinculado), CANT_TOTAL y LARGO
(manuales). Actualizar, reasignar, copiar y editar XX no sobrescribe los manuales.
LARGO incluye el prefijo en su texto (por ejemplo `L=368`); conservarlo al editar
el atributo. Así permanece unido al valor incluso al invertir el bloque.
Cantidad total y largo son atributos de una línea para editarlos directamente
en Ctrl+1 > Atributos. No tienen máscara propia. MARCA sigue siendo multilínea
con máscara. ACTUALIZAR-MARCAS convierte referencias DE antiguas sin ATTSYNC y
conserva sus valores; deseleccionar y volver a seleccionar refresca Propiedades.
La regresión verifica la migración de atributos multilínea y su persistencia
después de cambiar flip, copiar, actualizar y cambiar la marca.
Solo requiere marca única y diámetro positivo de la tabla; B y D son opcionales
para despiece, no para vista. El largo se conserva como se escribe, sin convertir
unidades. La disposición reserva espacios fijos para los atributos; comprobar
visualmente valores excepcionalmente largos antes de imprimir.

Ejecutar `python tools/cad/test_marcas_native.py --workflow detail` para comprobar
la inserción real por comando, atributos manuales, campos, copia, edición
automática de XX, cambio de filas, flip y anotatividad en una sesión desechable.
La prueba sustituye únicamente la selección gráfica de la tabla por su fixture.
También ejecuta la regresión de vista. No usa ni guarda dibujos del usuario.

Para regenerar la plantilla DE en una copia desechable con RomanD, cargar
`tools/cad/build_marca_sc.lsp` y `tools/cad/build_marca_de.lsp`, ejecutar
`(SCMDB:Build)` y exportar solo SINCAL_MARCA_DE_V1 con -WBLOCK. La opción de
autoría `--workflow build_detail` realiza esto y escribe el master del repositorio;
usar únicamente cuando no exista el archivo destino (no sobrescribe en silencio).

La nueva plantilla está autorizada en `sincal/runtime.py` y en `version.json`.
Las versiones antiguas del ejecutable cuya lista de recursos no incluya este
DWG requieren actualizar SINCAL o seleccionar el master manualmente en el
diálogo de MARCA-DE; actualizar solo el LISP no instala un master ausente.
