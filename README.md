# SINCAL Suite — Ingeniería y estándares CAD

**SINCAL Suite** es un workbench para Windows que centraliza estándares de dibujo para AutoCAD/ZWCAD, automatiza el procesamiento de planos y entrega herramientas de apoyo para ingeniería estructural y ubicación geográfica. La versión de producto es 2.0 y la secuencia técnica continúa en `v29.0.15` para conservar una actualización ordenada desde las instalaciones v28.

## Instalación web y distribución

SINCAL Suite se distribuye mediante un instalador web firmado. El archivo `Setup_SINCAL_v29.0.15.exe` contiene únicamente el motor de instalación; durante la ejecución descarga desde la release pública los paquetes exactos de la aplicación y del plugin AutoCAD, comprueba sus SHA-256 y recién entonces los instala.

El programa base no incorpora los 125 MB de mapas regionales. El paquete web sí contiene una copia inicial del master DWG, LISPs, startup, scripts, plumilla, calibración y ayuda estructural para que el primer arranque sea funcional. GitHub mantiene esos recursos al día mediante actualizaciones menores. Cada mapa regional se descarga solamente cuando se selecciona por primera vez en el módulo Ubicación.

Para instalar se necesita conexión a Internet y acceso HTTPS a `github.com` y `raw.githubusercontent.com`. Una vez descargados los componentes necesarios, las funciones instaladas continúan disponibles sin conexión.

## Primer inicio

1. Ejecuta el instalador oficial de la release `v29.0.15`.
2. Abre SINCAL; la aplicación comprobará automáticamente si existe una actualización menor de recursos.
3. Abre **Diagnóstico**, verifica el motor CAD sugerido y cámbialo si necesitas otra versión.
4. Pulsa **Preparar integración CAD**.
5. Reinicia AutoCAD/ZWCAD una vez para activar el cargador y las rutas de confianza.
6. Abre **Documentación** para consultar el manual buscable de comandos y módulos.

La copia base de los recursos esenciales queda junto a la aplicación. Las revisiones descargadas, estados, diagnósticos y registros se almacenan en `%LOCALAPPDATA%\SINCAL`: son datos internos de SINCAL que no necesitan acompañar el perfil móvil del usuario. La integración CAD activa se materializa en `%APPDATA%\Estandar SINCAL`: AutoCAD/ZWCAD deben poder encontrar allí LISPs, startup y scripts desde el perfil del usuario. No son dos copias equivalentes: **Local** es almacén y estado de la aplicación; **Roaming** es la copia operativa expuesta al CAD.

Al cerrar la ventana principal con **X**, SINCAL finaliza su proceso. La aplicación no se oculta en la bandeja ni permanece abierta en segundo plano.

## Componentes principales

### Home y Sincronizador

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

La interfaz usa GT Pressura para títulos y Helvetica Neue para textos, campos y tablas, sobre una base visual `ttkbootstrap`. **Ver → Tema** ofrece únicamente los modos corporativos Oscuro, Claro cálido y Sistema. El fondo es uniforme: gris cálido en oscuro y beige en claro, con mostaza o terracota para selección, realces y la sombra inferior derecha de los botones. La iconografía es monocroma, consistente y escalable; los íconos de acción muestran su función al pasar el mouse.

El diseño responde al ancho disponible con tres zonas: navegación lateral retráctil, contenido central con márgenes de lectura e índice contextual **En esta página** a la derecha. El índice es fijo, sin scrollbar, y navega por destinos reales de cada módulo. El menú lateral se oculta automáticamente en ventanas angostas sin eliminar las franjas laterales de descanso visual. Los tres controles `Aa` aplican zoom pequeño, normal o grande. El menú superior reúne **Archivo, Editar, Ver y Ayuda**; el historial de releases y commits está en Home y la única consola puede mostrarse u ocultarse en la parte inferior.

### Renombrado

La pestaña permite cargar una carpeta DWG/DXF, marcar archivos y renombrarlos por búsqueda y reemplazo. Se puede limpiar la ruta seleccionada en cualquier momento.

### Comandos en vivo

Este módulo envía una orden autónoma a los dibujos CAD abiertos. El glosario visible se limita a `BV`, `DL2`, `P0`, `PURGEALL`, `SETUP-A1`, `ST0`/`STO`, `W08`, `ZE` y `PLOTYA`. También puedes escribir un comando nativo, como `_QSAVE`, si confirmas que termina por sí solo y no solicita puntos, opciones ni respuestas. El campo acepta únicamente el nombre del comando, sin parámetros ni expresiones LISP. Usa Cancelar si necesitas detener el recorrido.

### Procesamiento DWG desde CMD

Pulsa **Preparar integración CAD** después de instalar o actualizar SINCAL y abre una ventana CMD nueva. En la carpeta del proyecto —puedes escribir `cmd` en la barra de direcciones del Explorador— ejecuta `AUDIT`, `ZE`, `PURGEALL`, `BV`, `DL2`, `PAGESETUP-A1` o `PUBLISH-A1`. Los lanzadores usan Windows PowerShell 5.1, incluido en Windows, y localizan el motor elegido mediante `%LOCALAPPDATA%\SINCAL\runtime\cad_engine.json`.

Con AutoCAD, SINCAL usa `accoreconsole.exe`. Con ZWCAD 2025/2026, crea una instancia COM aislada con `Visible = false`, abre cada plano, ejecuta el SCR, espera una señal de término, guarda, cierra y finaliza el proceso. Debes seleccionar **ZWCAD** en Diagnóstico, pulsar **Usar este motor** y volver a preparar la integración. ZWCAD debe estar instalado, activado y completamente cerrado antes de iniciar el lote; su automatización consume una licencia normal aunque no muestre interfaz. El lote se detiene si detecta una sesión ZWCAD abierta para no interferir con dibujos de trabajo. Conserva respaldos: estos comandos guardan cambios en todos los DWG de la carpeta.

### Conversión DXF

**Conversión DXF** es un módulo independiente: usa **Seleccionar DXF** para ver y escoger los archivos antes de cargarlos, o **Cargar carpeta** para listar todos los DXF de una ubicación. Marca solamente los deseados y conviértelos a DWG mediante una instancia CAD temporal. Cierra AutoCAD/ZWCAD antes de iniciarlo, conserva un respaldo y revisa los resultados en la consola Workbench.

### Generador de armadura

Prepara vistas, despieces y cubicación de fierro mediante comandos temporales enviados al CAD abierto:

- Estribos: separa **Estribo de entrada** y **Estribo de salida**, cada uno con su propio set de marcas, moldajes confirmados y cálculo. Cada estribo es una página continua: primero dimensiones y configuración; después revisión y marcas; finalmente despiece. El índice contextual permite saltar entre esas secciones. La zapata calcula las marcas 1–6, el suple 3-A opcional, empalmes 1–2/4–5 y las variantes excepcionales 2-A/5-A. Los diámetros se eligen desde una lista y los espaciamientos, origen de distribución, marcas y ganchos se editan únicamente en **Revisión y marcas**. La detección lee moldajes cerrados por vista (`FR_ZAP` a `EE_ZAP`), conserva sus vértices y exige `INSUNITS = 6`.
- Travesaños: extremos, cuadrantes sobre tope, macizos y viga; geometría y despiece.
- JSON de proyecto: importa parámetros compatibles y los convierte a las unidades de la interfaz.

Las vistas de zapata generan cotas coordinadas con `MARK`, `GSG_COTAS` y `GSG_MLEADER`. El **despiece general de zapata** se inserta en Model, agrupa los empalmes, acota parciales con `GSG_ARM-COTAS` y describe cada pieza con RomanD a 2,5 mm de papel. Cada grupo queda identificado de manera independiente; cuando sus parámetros cambian, AutoCAD/ZWCAD permite actualizarlo, conservarlo, aceptar todos los cambios o cancelar desde la línea de comandos.

Las sesiones guardan en un único archivo el estado editable del puente: JSON e instantánea verificable, ambos estribos, travesaños, reglas, marcas calculadas, pestaña activa y avance de vistas/despiece. **Abrir sesión**, **Guardar sesión** y **Nueva sesión** están bajo el título del generador; la biblioteca **Sesiones** permite buscar, ordenar y cargar proyectos anteriores. Los archivos formales se almacenan en `Documentos\SINCAL\Sesiones`; la recuperación automática se mantiene separada en `%LOCALAPPDATA%\SINCAL\sessions`. Los handles de moldaje se conservan sólo como referencia y siempre deben detectarse y confirmarse nuevamente en el DWG activo.

Los apartados **Muros**, **Consolas**, **Topes** y **Contrafuerte** ya forman parte de la página continua de cada estribo, aunque su generación geométrica permanece reservada para las etapas siguientes. Consulta **Documentación → Generador de armadura** para el glosario de capas (`FR_ZAP`, `AA_ZAP`, `CTF`, etc.), lectura de vistas y flujo de revisión. Verifica siempre dimensiones en cm, diámetros en mm y esviaje en grados.

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

El tab **Documentación** presenta el manual en el área central y usa el índice contextual derecho para navegar por sus temas. Contiene primer inicio, actualizaciones, integración CAD, startup, master DWG, inventario de recursos, todos los comandos LISP, procesamiento masivo, conversión DXF, módulo estructural, módulo de ubicación, diagnóstico y solución de problemas.

## Organización del repositorio

- `sincal/`: código de la aplicación.
  - `cad/`: comunicación CAD, detección de moldajes y generadores.
  - `rebar/`: modelo paramétrico y despiece de armaduras.
  - `ui/`: tema, iconos y pestañas de interfaz.
- `assets/`: fuentes e iconos incluidos en el paquete.
- `lisps/`, `scripts/`, `startup/`, `masters/`, `plotstyles/` y `mapas/`: recursos CAD publicables.
- `packaging/`: especificación PyInstaller, instalador Windows y certificado público.
- `src/`: plugin compilado para AutoCAD.
- `tests/`: pruebas automáticas y comprobación integral del runtime.
- `tools/`: compilación de releases y exportación segura al canal público.

`main.py`, `version.json` y `tutoriales.json` permanecen en la raíz como contratos estables de arranque, versión y actualización de recursos.

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

El proceso valida código y pruebas, compila y firma el plugin y la aplicación, crea los paquetes remotos, calcula hashes, compila el instalador web y genera el manifiesto y `SHA256SUMS.txt`. Cada compilación queda aislada en `installer_output/vXX.X.X/`; las versiones anteriores no se mezclan ni se eliminan. Para una compilación local no publicable se puede usar `-SkipSigning`.

En la release pública deben adjuntarse juntos:

- `Setup_SINCAL_v29.0.15.exe`
- `SINCAL_App_v29.0.15.zip`
- `SINCAL_AutoCAD_v29.0.15.zip`
- `release-manifest_v29.0.15.json`
- `SHA256SUMS.txt`

No renombres los paquetes después de compilar: el instalador usa URLs versionadas y hashes fijados en el momento del build.

## Seguridad y diagnóstico

El repositorio de desarrollo puede ser privado. El canal público contiene únicamente recursos autorizados y binarios de release; no recibe fuentes Python/.NET ni secretos. Protege `main`, limita el acceso de escritura y conserva la revisión de los LISPs y scripts, ya que son código ejecutable.

Los registros locales están en `%LOCALAPPDATA%\SINCAL\logs\sincal.log` y los incidentes estructurados en `%LOCALAPPDATA%\SINCAL\diagnostics\incidents.jsonl`. Ninguno se transmite automáticamente. Si los comandos CAD no aparecen, actualiza recursos, ejecuta Diagnóstico, vuelve a preparar la integración y reinicia CAD. Si una descarga falla, revisa conexión, proxy y antivirus antes de reintentar.
