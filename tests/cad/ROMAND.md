# ROMAND

`ROMAND` acepta una preselección de TEXT/MTEXT o pide seleccionarlos. Enter sin
selección configura únicamente el estilo. Usa RomanD, `romand.shx`, anotativo,
altura de papel 2,5, factor de ancho 0,8, sin inclinación ni efectos.

Conserva contenido, punto de inserción/alineación, giro y justificación. En MTEXT
retira las sustituciones internas de fuente, altura, ancho e inclinación, pero
conserva párrafos, colores y fracciones. Omite capas bloqueadas, TEXT con
justificación Alineado/Ajustado y MTEXT con campos; informa cuántos omitió.
Estos últimos se conservan completos porque reescribir su formato mediante
ActiveX en ZWCAD puede convertir los campos en texto literal.

La comprobación del estilo lee toda la XDATA y compara los nombres de las
aplicaciones sin distinguir mayúsculas. El filtro específico de `entget` omite
`AcadAnnotative` en ciertos dibujos heredados de ZWCAD y causaba un rechazo
incorrecto de una configuración válida.

## Verificación

Ejecutar `tools/cad/test_romand_native.py` con `--engine` apuntando a
`accoreconsole.exe` (AutoCAD 2025/2027) o `ZWCAD.exe` (2026). Para ZWCAD,
`--drawing archivo.dwg` prueba una copia temporal del archivo; nunca guarda el
original. El proceso de prueba se cierra al terminar. No usa la sesión abierta.

Pruebas nativas: creación y reparación del estilo, idempotencia, conservación
de otros estilos y textos no seleccionados, TEXT justificado, MTEXT con formato
interno, altura a escala 1:100 y preservación de MTEXT con campos. Los campos se
comprueban en ZWCAD; Core Console no ofrece el ActiveX necesario para crearlos.

Comprobación interactiva adicional: ejecutar con preselección y sin ella,
Enter sin selección, cancelar con Esc y deshacer la operación con U.
