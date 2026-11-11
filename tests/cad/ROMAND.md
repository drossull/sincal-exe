# ROMAND

`ROMAND` acepta una preselección de TEXT/MTEXT o pide seleccionarlos. Enter sin
selección configura únicamente el estilo. Usa RomanD TrueType, `romand__.ttf`, anotativo,
altura de papel 2,5, factor de ancho 0,8, sin inclinación ni efectos.
Requiere esa fuente instalada. Si falta, avisa sin sustituirla por una SHX.
La asignación final se hace al registro STYLE con la familia RomanD, porque
`-STYLE` rechaza ese archivo reservado para el editor MTEXT. Se almacena el
nombre registrado `romand__.ttf`; ZWCAD no resuelve su familia al usar la ruta
absoluta. La prueba nativa comprueba también el nombre de familia con GetFont.

Conserva contenido, punto de inserción/alineación, giro y justificación. En MTEXT
retira las sustituciones internas de fuente, altura, ancho e inclinación, pero
conserva párrafos, colores y fracciones. Admite MTEXT con campos, incluidas
fórmulas y propiedades vinculadas a otros objetos. Omite capas bloqueadas,
TEXT con justificación Alineado/Ajustado y campos que el CAD no puede leer;
informa cuántos omitió.

Los campos se leen mediante `FieldCode`, conservando expresiones y referencias.
Después de aplicar las propiedades del texto, se vacía y repone el código
completo para que ZWCAD reconstruya campos activos. No se vuelve a modificar
el contenido mediante `entmod` después de ese paso. Se evalúan y verifican
las fórmulas y los objetos referenciados; un fallo revierte la operación.

La comprobación del estilo lee toda la XDATA y compara los nombres de las
aplicaciones sin distinguir mayúsculas. El filtro específico de `entget` omite
`AcadAnnotative` en ciertos dibujos heredados de ZWCAD y causaba un rechazo
incorrecto de una configuración válida.

## Verificación

Ejecutar `tools/cad/test_romand_native.py` con `--engine` apuntando a
`accoreconsole.exe` (AutoCAD 2025/2027) o `ZWCAD.exe` (2026). Para ZWCAD,
`--drawing archivo.dwg` prueba una copia temporal del archivo; nunca guarda el
original. El proceso de prueba se cierra al terminar. No usa la sesión abierta.

Pruebas nativas: creación TrueType y conversión del estilo SHX anterior, idempotencia, conservación
de otros estilos y textos no seleccionados, TEXT justificado, MTEXT con formato
interno, altura a escala 1:100 y formato de MTEXT con campos. Se cambia una
línea vinculada de longitud 100 a 175 y se verifica que el campo se actualice,
también después de volver a aplicar ROMAND. Los campos se
comprueban en ZWCAD; Core Console no ofrece el ActiveX necesario para crearlos.

Comprobación interactiva adicional: ejecutar con preselección y sin ella,
Enter sin selección, cancelar con Esc y deshacer la operación con U.
