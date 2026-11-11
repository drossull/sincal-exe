# Editor de revisiones en dibujos abiertos

`REV-EDIT` y el pinzamiento **Editar revisiones** abren la misma ventana.
El complemento debe estar cargado en AutoCAD o ZWCAD. El pinzamiento aparece
al seleccionar una inserción `VIÑETA` / `VINETA` que contenga una tabla nativa
de seis columnas con el Field `CustomDP.Revision` en su primera celda.

## Compilación e instalación local

```powershell
./tools/build_revision_grip.ps1 -InstallForCurrentUser
```

El script detecta los SDK instalados y compila un binario para cada versión.
La instalación copia los binarios, `REV-EDIT.lsp` y el startup a la integración
CAD del usuario. En una sesión nueva se cargan automáticamente; en una sesión
ya abierta se puede cargar `REV-EDIT.lsp` con `APPLOAD`. Si una versión anterior
de la DLL ya está cargada, hay que cerrar y volver a abrir CAD para sustituirla.

Las DLL viajan con la aplicación instalada. Actualizar únicamente los recursos
LISP no distribuye este complemento nativo.

La pestaña **Propiedades personalizadas** también se abre con `PROPS-EDIT`,
sin seleccionar una viñeta. Marca los nombres que quieras aplicar, edita sus
valores y selecciona los DWG de destino. Crear propiedades faltantes y dejar
valores vacíos es explícito; no se eliminan ni renombran propiedades. Cada
botón Aplicar opera sólo sobre su pestaña activa y no guarda los dibujos.

## Comportamiento

- La fuente es la viñeta elegida. Su tabla, estilos, dimensiones y Fields se
  conservan; las celdas vinculadas modifican sus propiedades DWGPROPS.
- Las propiedades DWG son globales y las inserciones de una misma definición
  comparten su tabla. El diálogo informa este alcance.
- El dibujo actual se marca inicialmente. Los demás destinos se eligen en la
  lista de documentos abiertos en la misma instancia CAD.
- Aplicar copia la tabla completa, incluido el historial, en las tablas
  compatibles de cada destino seleccionado. No agrega ni elimina filas.
- Un destino de solo lectura, incompatible o cuyo contenido cambió después de
  la lectura se rechaza. Se informa el resultado de cada dibujo.
- No se guardan ni se cierran dibujos. No se garantiza que un solo `U` revierta
  conjuntamente tabla y DWGPROPS; los valores se pueden corregir en el editor.

## Verificación nativa

`tests/cad/RevisionGripSmoke.cs` solo se incluye con
`-p:RevisionGripTests=true`. Compilar a una carpeta temporal y colocar esa DLL
de pruebas en una ruta de confianza ya existente; no cambiar `SECURELOAD`.
Asigna un nombre de ensamblado exclusivo mediante `-p:AssemblyName=...`
(por ejemplo, `Sincal.RevisionGrip.TEST.Properties.AutoCAD`) para que la DLL
de producción cargada por el startup no oculte los comandos de prueba.

```powershell
python tools/cad/test_revision_grip_native.py --progid AutoCAD.Application.25.1 --dll RUTA_DLL_PRUEBAS
python tools/cad/test_revision_grip_native.py --progid ZWCAD.Application.2026 --dll RUTA_DLL_PRUEBAS
```

El runner crea una instancia propia oculta y copias temporales. Comprueba el
pinzamiento y su tooltip, edición de Fields/DWGPROPS e historial, destino
inactivo y documento omitido, rechazo de datos inválidos y snapshots antiguos,
reversión ante un fallo inyectado después de escribir y antes de confirmar,
el funcionamiento normal de `U`/`REDO` con un círculo y ausencia de guardado.
La restauración del editor con un solo `U` se registra como observación.
El inyector sólo existe en la DLL de pruebas. Cierra
solo la instancia creada y verifica que el master no cambió. La prueba del
diálogo pulsa el pinzamiento mediante su API, inspecciona sus controles y
cancela para comprobar que ningún dibujo cambia. No toma capturas.

Para la revisión manual: seleccionar la viñeta, pulsar el pinzamiento, cambiar
una propiedad y una fila histórica, marcar otro DWG y dejar un tercero sin
marcar. Verificar los resultados en cada destino. Cancelar debe
conservar todos los documentos.

Para comprobar sólo el nuevo flujo de propiedades, usa el mismo runner con
`--suite properties`. Crea cinco dibujos temporales sin viñeta, con Fields en
MTEXT y atributos; verifica selección, mayúsculas de claves, faltantes, vacíos,
propiedades ajenas, sólo lectura, rechazo de datos obsoletos y rollback. Abre
`PROPS-EDIT` y cancela su segunda pestaña. No repite las pruebas de revisiones.

La interfaz también se comprueba sin abrir CAD ni mostrar ventanas:

```powershell
dotnet run --project tests/cad/RevisionDialogStandalone.csproj -f net10.0-windows
dotnet run --project tests/cad/RevisionDialogStandalone.csproj -f net48
```
