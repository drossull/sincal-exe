# Distribución opcional de Pasarela BIM

Pasarela BIM se construye como `SINCAL-Pasarela.exe`, separado de los ejecutables
principales de SINCAL. No incluye FreeCAD, AutoCAD ni el runtime OCR.

## Compilar únicamente el módulo

Desde la raíz del repositorio, con Python, PyInstaller e Inno Setup disponibles:

```powershell
python tools/build_pasarela_module.py --smoke-test
```

El comando genera en `installer_output/pasarela-bim/v0.3.2/`:

- `SINCAL_Pasarela_v0.3.2.zip`: ejecutable y `module.json`, con hashes SHA-256 de
  todos los archivos del paquete excepto el propio manifiesto.
- `Setup_SINCAL_Pasarela_v0.3.2.exe`: complemento instalable posteriormente,
  por usuario y sin privilegios de administrador.
- `pasarela-module-build.json`: rutas, tamaños y hash del ZIP para preparar la distribución.
- `smoke-test.json`: resultado de la comprobación de la interfaz del ejecutable real.

Este comando local **no firma los artefactos**. Para publicar, usa
`build_release.ps1` sin `-SkipSigning`: firma el ejecutable antes de calcular su
manifiesto y ZIP; posteriormente firma también el instalador complementario.

`--skip-installer` genera sólo el ejecutable y ZIP. `--skip-build` vuelve a empaquetar
el ejecutable existente, útil después de firmarlo. `--output-dir` permite escoger
la carpeta de salida. El empaquetado no compila los proyectos CAD ni OCR.

## Instalación y datos

El instalador principal ofrece el componente desmarcado por defecto. Sólo si se
selecciona descarga el ZIP, verifica el SHA-256 de la release e instala el módulo
en `{app}/modules/pasarela-bim`. `-SkipPasarelaModule` permite construir la release
principal sin ofrecer este componente.

El complemento posterior instala en `%LOCALAPPDATA%/SINCAL/modules/pasarela-bim`.
El anfitrión prioriza esa instalación sobre la ubicada junto a SINCAL. El editor
se abre desde el menú de SINCAL; el instalador del complemento no crea un acceso
independiente que abra el navegador.

Los modelos y resultados se guardan fuera del módulo, en
`%LOCALAPPDATA%/SINCAL/pasarela-bim/generados`, salvo que se configure
`PASARELA_DATA_DIR`. La desinstalación del complemento no elimina esos datos ni
FreeCAD. Los recursos web y el motor Python propio se incluyen en el ejecutable;
FreeCAD importa este motor desde la extracción privada de PyInstaller.

El contrato del manifiesto es `schema: 1`, `id: "pasarela-bim"`, `host_api: 1`,
`version: "0.3.2"`, `embedding: 1` y `entrypoint: "SINCAL-Pasarela.exe"`. La versión es independiente
de la aplicación principal. El paquete se limita a 150 MiB comprimidos y 512 MiB
instalados.

## Editor integrado

SINCAL DesktopWeb aloja el editor en un panel persistente: cambiar de módulo no
recarga el proyecto. El anfitrión arranca el proceso sin navegador y vincula su
origen local mediante un token privado. La política de contenido del módulo
permite únicamente ese anfitrión; en modo independiente no admite incrustación.
Los módulos anteriores muestran una acción de actualización antes de abrirse.
