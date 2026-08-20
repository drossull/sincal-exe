# SINCAL — Suite de Ingeniería y Estándares CAD

**SINCAL 2.0** es un workbench para Windows que centraliza estándares de dibujo para AutoCAD/ZWCAD, automatiza el procesamiento de planos y entrega herramientas de apoyo para ingeniería estructural y ubicación geográfica. La marca del producto es 2.0 y la secuencia técnica continúa en `v29.0.0` para conservar una actualización ordenada desde las instalaciones v28.

## Instalación web y distribución

SINCAL se distribuye mediante un instalador web firmado. El archivo `Setup_SINCAL_v29.0.0.exe` contiene únicamente el motor de instalación; durante la ejecución descarga desde la release pública los paquetes exactos de la aplicación y del plugin AutoCAD, comprueba sus SHA-256 y recién entonces los instala.

El programa base no incorpora los 125 MB de mapas regionales. El paquete web sí contiene una copia inicial del master DWG, LISPs, startup, scripts, plumilla, calibración y ayuda estructural para que el primer arranque sea funcional. GitHub mantiene esos recursos al día mediante actualizaciones menores. Cada mapa regional se descarga solamente cuando se selecciona por primera vez en el módulo Ubicación.

Para instalar se necesita conexión a Internet y acceso HTTPS a `github.com` y `raw.githubusercontent.com`. Una vez descargados los componentes necesarios, las funciones instaladas continúan disponibles sin conexión.

## Primer inicio

1. Ejecuta el instalador oficial de la release `v29.0.0`.
2. Abre SINCAL; la aplicación comprobará automáticamente si existe una actualización menor de recursos.
3. Abre **Diagnóstico**, verifica el motor CAD sugerido y cámbialo si necesitas otra versión.
4. Pulsa **Preparar integración CAD**.
5. Reinicia AutoCAD/ZWCAD una vez para activar el cargador y las rutas de confianza.
6. Abre **Documentación** para consultar el manual buscable de comandos y módulos.

La copia base de los recursos esenciales queda junto a la aplicación. Las revisiones descargadas se almacenan en `%LOCALAPPDATA%\SINCAL\resources` y la integración CAD activa se materializa en `%APPDATA%\Estandar SINCAL`.

Al cerrar la ventana principal con **X**, SINCAL finaliza su proceso. La aplicación no se oculta en la bandeja ni permanece abierta en segundo plano.

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

### Interfaz Workbench

La interfaz usa un menú lateral retráctil con tamaño **Compacto**, **Estándar** o **Amplio**. El orden de trabajo es Sincronizador, Documentación, Procesamiento masivo, Ubicación y Módulo estructural; Conversión DXF y Diagnóstico permanecen como herramientas complementarias. La consola se puede ocultar o acoplar al borde inferior o derecho desde la cabecera, y concentra todos los resultados de éxito, término y error.

### Procesamiento masivo

La pestaña permite cargar una carpeta DWG/DXF, marcar archivos, renombrarlos por búsqueda y reemplazo, enviar comandos a dibujos abiertos y procesar DWG cerrados. Ya no tiene una consola propia: los procesos escriben en la consola Workbench acoplable.

Acciones disponibles sobre planos cerrados: Auditar, Purgar, Encuadrar vista, Eliminar Layout2/A1, Bloquear viewports, Configurar layouts A1 y Plotear PDF A1. Antes de ejecutarlas, guarda un respaldo, prepara la integración y cierra completamente AutoCAD/ZWCAD. Los botones de automatización cerrada recorren todos los DWG de la carpeta seleccionada.

SINCAL registra en `%LOCALAPPDATA%\SINCAL\runtime\cad_engine.json` el ejecutable elegido y lo entrega directamente a PowerShell. `cad_wrapper.bat` se conserva sólo para compatibilidad. Cada proceso deja motor, versión, código de salida, duración y últimas líneas de error en el registro local de incidentes.

### Conversión DXF

**Conversión DXF** es un módulo independiente: selecciona una carpeta, marca solamente los DXF deseados y convierte cada uno a DWG mediante una instancia CAD temporal. Cierra AutoCAD/ZWCAD antes de iniciarlo, conserva un respaldo y revisa los resultados en la consola Workbench.

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

### Diagnóstico y soporte

La pestaña **Diagnóstico** comprueba recursos esenciales, LISPs, CMD, PowerShell, permisos de escritura, procesos CAD y todas las instalaciones AutoCAD/ZWCAD detectadas. Permite seleccionar explícitamente el motor usado por el procesamiento masivo.

El botón **Generar informe ZIP** crea `diagnostico.json`, `resumen.txt`, una copia limitada del log y una declaración de privacidad. El informe no incorpora DWG ni credenciales y sustituye usuario, equipo, correo y ruta del proyecto por marcadores anónimos. Los informes permanecen locales hasta que el usuario decide enviarlos.

### Documentación integrada

El tab **Documentación** ofrece búsqueda por comando, herramienta o palabra clave. Contiene primer inicio, actualizaciones, integración CAD, startup, master DWG, inventario de recursos, todos los comandos LISP, procesamiento masivo, conversión DXF, módulo estructural, módulo de ubicación, diagnóstico y solución de problemas.

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

- `Setup_SINCAL_v29.0.0.exe`
- `SINCAL_App_v29.0.0.zip`
- `SINCAL_AutoCAD_v29.0.0.zip`
- `release-manifest_v29.0.0.json`
- `SHA256SUMS.txt`

No renombres los paquetes después de compilar: el instalador usa URLs versionadas y hashes fijados en el momento del build.

## Seguridad y diagnóstico

El repositorio de desarrollo puede ser privado. El canal público contiene únicamente recursos autorizados y binarios de release; no recibe fuentes Python/.NET ni secretos. Protege `main`, limita el acceso de escritura y conserva la revisión de los LISPs y scripts, ya que son código ejecutable.

Los registros locales están en `%LOCALAPPDATA%\SINCAL\logs\sincal.log` y los incidentes estructurados en `%LOCALAPPDATA%\SINCAL\diagnostics\incidents.jsonl`. Ninguno se transmite automáticamente. Si los comandos CAD no aparecen, actualiza recursos, ejecuta Diagnóstico, vuelve a preparar la integración y reinicia CAD. Si una descarga falla, revisa conexión, proxy y antivirus antes de reintentar.
