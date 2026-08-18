# SINCAL — Suite de Ingeniería y Estándares CAD

**SINCAL Suite 1.0** es una aplicación para Windows que centraliza estándares de dibujo para AutoCAD/ZWCAD, automatiza el procesamiento de planos y entrega herramientas de apoyo para ingeniería estructural y ubicación geográfica. La versión del producto se mantiene como 1.0 y la secuencia técnica continúa en `v28.0.3` para conservar la actualización desde instalaciones históricas v27.

## Instalación web y distribución

SINCAL se distribuye mediante un instalador web firmado. El archivo `Setup_SINCAL_v28.0.3.exe` contiene únicamente el motor de instalación; durante la ejecución descarga desde la release pública los paquetes exactos de la aplicación y del plugin AutoCAD, comprueba sus SHA-256 y recién entonces los instala.

El programa base no incorpora los 125 MB de mapas regionales. El master DWG, LISPs, startup, scripts, plumilla y calibración se descargan desde el canal público al iniciar. Cada mapa regional se descarga solamente cuando se selecciona por primera vez en el módulo Ubicación.

Para instalar se necesita conexión a Internet y acceso HTTPS a `github.com` y `raw.githubusercontent.com`. Una vez descargados los componentes necesarios, las funciones instaladas continúan disponibles sin conexión.

## Primer inicio

1. Ejecuta el instalador oficial de la release `v28.0.3`.
2. Abre SINCAL y acepta la actualización inicial de recursos CAD.
3. Pulsa **Preparar integración CAD**.
4. Reinicia AutoCAD/ZWCAD una vez para activar el cargador y las rutas de confianza.
5. Abre **Documentación** para consultar el manual buscable de comandos y módulos.

Los recursos se almacenan en `%LOCALAPPDATA%\SINCAL\resources` y la integración CAD activa se materializa en `%APPDATA%\Estandar SINCAL`.

## Componentes principales

### Sincronizador

- Comprueba una nueva versión completa desde las Releases públicas.
- Revisa recursos al iniciar y cada minuto mediante un manifiesto liviano.
- Descarga LISPs, startup, scripts, CTB, master, tutoriales y mapas autorizados.
- Valida tipo, tamaño y SHA de Git antes de activar cada archivo.
- Prepara el cargador de AutoCAD/ZWCAD y la consola para procesos cerrados.

### Recursos CAD

- `lisps/`: comandos interactivos de dibujo, cotas, viewports, propiedades y estandarización.
- `startup/`: variables protegidas, propiedades de viñeta, escalas en metros y colores C0–C9.
- `masters/FORMATOS ANOTATIVOS ACAD_2025.dwg`: bloques, viñetas, capas y estilos oficiales.
- `scripts/`: automatización BAT, PowerShell y SCR.
- `plotstyles/`: plumilla `SINCAL_A1 (2025).ctb`.
- `mapas/`: calibración, ayuda y mapas regionales bajo demanda.
- `tutoriales.json`: contenido estructurado del manual integrado.

### Procesamiento masivo

La pestaña permite cargar una carpeta DWG/DXF, marcar archivos, renombrarlos por búsqueda y reemplazo, convertir DXF a DWG, enviar comandos a dibujos abiertos y procesar DWG cerrados.

Acciones disponibles sobre planos cerrados: Auditar, Purgar, Encuadrar vista, Eliminar Layout2/A1, Bloquear viewports, Configurar layouts A1 y Plotear PDF A1. Antes de ejecutarlas, guarda un respaldo, prepara la integración y cierra completamente AutoCAD/ZWCAD. Los botones de automatización cerrada recorren todos los DWG de la carpeta seleccionada.

### Módulo estructural

Genera vistas y despieces de armaduras mediante comandos temporales enviados al CAD abierto:

- Estribos: geometría de zapata, recubrimientos, mallas y vistas Frontal/A/B/C.
- Travesaños: extremos, cuadrantes sobre tope, macizos y viga; geometría y despiece.
- JSON de proyecto: importa parámetros compatibles y los convierte a las unidades de la interfaz.

Las pestañas **Muros** y **Consola y Topes** están reservadas actualmente y todavía no generan elementos. Verifica siempre dimensiones en cm, diámetros en mm y esviaje en grados.

### Módulo de ubicación

Lee puntos desde un KMZ de Google Earth, permite escoger un mapa MOP calibrado y genera un PNG con la posición marcada. El flujo es:

1. Cargar KMZ.
2. Seleccionar el Placemark.
3. Elegir la región correspondiente.
4. Aplicar microajuste opcional en píxeles.
5. Generar y guardar el croquis.

La primera utilización de una región solicita descargar su mapa y lo valida antes de guardarlo localmente.

### Documentación integrada

El tab **Documentación** ofrece búsqueda por comando, herramienta o palabra clave. Contiene este README, primer inicio, actualizaciones, integración CAD, startup, master DWG, inventario de recursos, todos los comandos LISP, procesamiento masivo, módulo estructural, módulo de ubicación y solución de problemas.

## Publicar una actualización menor

1. Modifica un recurso autorizado en el repositorio privado de desarrollo.
2. Para el master, trabaja sobre una copia y valida bloques, atributos y referencias antes de reemplazarlo.
3. Haz commit y push a `main`.
4. El workflow `publish-distribution.yml` exportará únicamente la lista blanca a `drossull/sincal-updates` y actualizará `manifest.json`.
5. SINCAL detectará la nueva revisión dentro del siguiente ciclo de un minuto y ofrecerá instalarla.

Los cambios en Python, interfaz, plugin .NET o instalador requieren una release completa. Los recursos menores no reemplazan ejecutables.

## Compilar una release web

```powershell
python -m pip install -r requirements-build.txt
pwsh -NoProfile -File tools/build_release.ps1
```

El proceso valida código y pruebas, compila y firma el plugin y la aplicación, crea los paquetes remotos, calcula hashes, compila el instalador web y genera el manifiesto y `SHA256SUMS.txt`. Para una compilación local no publicable se puede usar `-SkipSigning`.

En la release pública deben adjuntarse juntos:

- `Setup_SINCAL_v28.0.3.exe`
- `SINCAL_App_v28.0.3.zip`
- `SINCAL_AutoCAD_v28.0.3.zip`
- `release-manifest_v28.0.3.json`
- `SHA256SUMS.txt`

No renombres los paquetes después de compilar: el instalador usa URLs versionadas y hashes fijados en el momento del build.

## Seguridad y diagnóstico

El repositorio de desarrollo puede ser privado. El canal público contiene únicamente recursos autorizados y binarios de release; no recibe fuentes Python/.NET ni secretos. Protege `main`, limita el acceso de escritura y conserva la revisión de los LISPs y scripts, ya que son código ejecutable.

Los registros locales están en `%LOCALAPPDATA%\SINCAL\logs\sincal.log`. Si los comandos CAD no aparecen, actualiza recursos, vuelve a preparar la integración y reinicia CAD. Si una descarga falla, revisa conexión, proxy y antivirus antes de reintentar.
