# SINCAL Suite — Ingeniería y estándares CAD

**SINCAL Suite** es una aplicación para Windows que centraliza estándares de dibujo para AutoCAD/ZWCAD, automatiza el procesamiento de planos y entrega herramientas de apoyo para ingeniería estructural y ubicación geográfica. La versión de producto es 3.0. Esta guía corresponde a la release `v3.0.28`, con interfaz de escritorio web y Pasarela BIM como módulo opcional.

La disponibilidad de los instaladores se confirma en las
[publicaciones oficiales](https://github.com/drossull/sincal-updates/releases).
La actualización de esta guía no implica por sí sola que una release ya esté publicada.

## Aplicación de escritorio con interfaz web

La aplicación funciona localmente en Windows. La interfaz
HTML/CSS se muestra dentro de una ventana propia mediante Microsoft Edge WebView2.
Para ejecutarla desde el repositorio durante el desarrollo:

```powershell
python -m pip install -r requirements-desktop-web.txt
python -m sincal.web.desktop
```

Requiere Microsoft Edge WebView2 Runtime instalado. Después de instalar las
dependencias, la interfaz y sus operaciones locales funcionan sin Internet;
las descargas de recursos, actualizaciones y módulos requieren conexión.
Al cerrar la ventana se pide confirmación y se apaga el servidor interno. Sus
sesiones se mantienen en el almacén privado del perfil de Windows.

## Funciones de la interfaz de escritorio

La interfaz reúne los módulos del menú y reutiliza los cálculos, recursos y
generadores Python/LISP existentes. Pasarela BIM se instala como módulo opcional
y se utiliza dentro de la misma ventana de SINCAL.

- **Home:** presentación, comprobación/aplicación de recursos, preparación CAD
  e historial de operaciones con descarga del registro.
- **Documentación:** búsqueda en contenido e índice agrupado por categorías;
  instrucciones adaptadas a los controles de esta interfaz.
- **Comandos en vivo:** glosario, Enter para ejecutar, comando autónomo personalizado,
  dibujo activo o recorrido secuencial de todos los dibujos confirmados.
- **Conversión DXF–DWG:** selección nativa múltiple, carpeta de salida, elección
  AutoCAD/ZWCAD, instancia temporal y rechazo de sobrescrituras. Requiere cerrar CAD.
- **Renombrado:** selección de carpeta, vista previa, comprobación de colisiones,
  revalidación antes de aplicar e intento de reversión si falla.
- **Ubicación:** KML/KMZ, selección de punto/mapa, ajustes y exportación PNG con
  calibración existente. No interpreta coordenadas PTL como geográficas.
- **Consulta:** JSON de solo lectura, OT/revisión/estructura y exportación TXT;
  dimensiones compatibles del JSON se convierten de mm a cm para las armaduras.
- **Pasarela BIM:** módulo opcional con estado de instalación, descarga del paquete
  compatible y acceso al editor topológico de pasarelas de hormigón.
- **Armaduras:** entrada/salida independientes, marcas editables, diámetros,
  separación, ganchos, origen, cantidades, áreas, pesos, tabla ampliada y detalle
  SVG por marca. Dibujo de vistas FR/AA/BB/CC/EE y despiece de zapata.
- **Travesaños:** los cinco cuadrantes y sus despieces, con los generadores
  extraídos sin alterar sus plantillas a `sincal/cad/crossbeam.py`.
- **Prospecciones:** extracción PDF/TXT y OCR local, tablas, avisos, imagen/texto
  de evidencia, confianza por celda, cotejo explícito, vista del perfil e inserción CAD.
- **Sesiones:** instantáneas privadas por perfil Windows, búsqueda, tarjetas,
  paginación, carga, importación no destructiva de sesiones anteriores, exportación,
  recuperación periódica y oferta de reabrir el último guardado.
- **Diagnóstico:** resumen/ZIP redactado y detección/selección del motor de scripts.

La conexión usa COM en procesos aislados. La comprobación tiene límite de
15 segundos y nunca inicia CAD. Cada envío revalida instancia y dibujo;
los moldajes se vuelven a comprobar antes de generar. Una orden incierta no se
reenvía automáticamente. Cancelar deja de esperar, no deshace una orden enviada
ni mata CAD. El comando elegido puede guardar/exportar por sí mismo: el retorno
de control no certifica que haya producido un dibujo correcto.

La interfaz conserva fuentes locales, paletas de Cadence, modos oscuro/claro/
sistema, zoom 90/100/115 %, paneles ocultables por separado, márgenes de lectura,
botones rectos con sombra y una animación vectorial de actividad. El progreso
muestra porcentaje solamente cuando existe una medida real. Preferencias y
sesiones permanecen en `%LOCALAPPDATA%\SINCAL\web-pilot\sessions.sqlite3`.
Quienes comparten una cuenta Windows comparten ese almacén; no hay cuentas
remotas ni sincronización en nube.

Los trabajos generan registros JSONL redactados en `web-pilot/logs`, con máximo
100 registros y 30 días; los temporales propios de `web-pilot/operations` vencen
a los 7 días. No se borran DWG ni sesiones formales. Los archivos solo se autorizan
mediante selección nativa, con identificadores opacos; la API no acepta rutas de
disco ni comandos de shell arbitrarios. Host, Origin y token se verifican.

Para pruebas de frontend también existe `python -m sincal.web.server`, que abre
un navegador **solo para desarrollo**. El arranque normal es la ventana nativa.
El servidor se limita a loopback: no es apto para publicarlo en Internet.

### Validación y compilación

El arranque de escritorio usa `desktop_main.py` y
`packaging/windows/SINCAL_Web.spec`. La release `v3.0.28` se construye con
`tools/build_release.ps1 -DesktopWeb`; sin esa opción, el pipeline conserva el
arranque Tk para compatibilidad. La versión instalada sólo cambia al ejecutar
su instalador.

Cada publicación debe identificar sus pruebas y limitaciones. Antes de publicarla
se comprueban el ejecutable empaquetado, WebView2, los paquetes firmados y las
operaciones modificadas sobre archivos de ensayo. El documento
[Estado de la migración](docs/MIGRACION_WEB.md) conserva antecedentes técnicos;
sus pendientes históricos no sustituyen el resultado de verificación de cada release.

## Instalación web y distribución

SINCAL Suite se distribuye mediante un instalador web firmado. El archivo
`Setup_SINCAL_v3.0.28.exe` descarga desde su release pública los paquetes exactos
de la aplicación y del plugin AutoCAD, comprueba sus SHA-256 y después los instala.
El componente **Pasarela BIM** aparece **desmarcado por defecto**: su paquete
independiente sólo se descarga si se selecciona. También puede instalarse más adelante.

El programa base no incorpora los 125 MB de mapas regionales. El paquete web sí contiene una copia inicial del master DWG, LISPs, startup, scripts, plumilla, calibración y ayuda estructural para que el primer arranque sea funcional. GitHub mantiene esos recursos al día mediante actualizaciones menores. Cada mapa regional se descarga solamente cuando se selecciona por primera vez en el módulo Ubicación.

Para instalar se necesita conexión a Internet y acceso HTTPS a `github.com` y `raw.githubusercontent.com`. Una vez descargados los componentes necesarios, las funciones instaladas continúan disponibles sin conexión.

## Primer inicio

1. Descarga y ejecuta el instalador de `v3.0.28` desde su publicación oficial, con SINCAL y CAD cerrados.
2. Abre SINCAL; la aplicación comprobará automáticamente si existe una actualización menor de recursos.
3. Abre **Diagnóstico**, verifica el motor CAD sugerido y cámbialo si necesitas otra versión.
4. Pulsa **Preparar integración CAD**.
5. Reinicia AutoCAD/ZWCAD una vez para activar el cargador y las rutas de confianza.
6. Abre **Documentación** para consultar el manual buscable de comandos y módulos.
7. Si necesitas Pasarela BIM y figura **No instalado**, abre su página y pulsa
   **Instalar Pasarela BIM**. Se descargará el módulo correspondiente a esta
   versión de SINCAL; al terminar podrás usar **Abrir editor**.

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

La interfaz comparte el sistema visual de Cadence sobre `ttkbootstrap`: Roboto para lectura, Roboto Condensed para títulos, Roboto Flex para botones y Roboto Mono para campos numéricos y consola. El cuerpo base es de 14 píxeles lógicos; Tk y ttk sincronizan sus tamaños con el zoom y el DPI de CustomTkinter. Las fuentes TrueType se cargan privadamente, sin cambiar el suavizado global de Windows; el motor Tk no reproduce exactamente el rasterizado de un navegador.

Al pie del menú izquierdo, el selector ofrece las mismas 16 familias de Cadence: Cadence, Bootstrap, PyData, Nord, Solarized, Catppuccin, Gruvbox, Dracula, Tokyo Night, One, Everforest, Vapor, Minty, Pulse, United y Sandstone. El botón sol/luna alterna claro/oscuro sin cambiar la familia. **Ver → Tema → Del sistema** sigue la apariencia del equipo. Las preferencias se conservan en `%LOCALAPPDATA%\SINCAL\ui_preferences.json`. Cambiar tema no reconstruye los formularios ni descarta cambios pendientes.

El diseño responde al ancho disponible con tres zonas: navegación lateral retráctil, contenido central con márgenes de lectura e índice contextual **En esta página** a la derecha. El índice es fijo, sin scrollbar, y navega por destinos reales de cada módulo. El botón superior de menú oculta/restaura ambos paneles, con una transición cancelable de 180 ms; las ventanas angostas los ocultan automáticamente. Los botones con sombra tienen respuesta breve al pasar el mouse y pulsar. **Ver → Reducir movimiento** desactiva estas transiciones; también se respeta la preferencia de animaciones de Windows. **Ver → Zoom texto** ofrece 90 %, 100 % y 115 %. El historial está en Home y la consola opcional permanece abajo.

### Renombrado

La pestaña permite cargar una carpeta DWG/DXF, marcar archivos y renombrarlos por búsqueda y reemplazo. Se puede limpiar la ruta seleccionada en cualquier momento.

### Comandos en vivo

La interfaz comparte el lenguaje visual de Cadence: fondo carbón o beige cálido,
acentos corporativos, separadores finos, controles rectos y botones con sombra
desplazada. Usa Roboto para lectura y Roboto Condensed para títulos; ambas fuentes
se incluyen con la aplicación. La animación conserva su rótulo Pressura.

Este módulo envía una orden autónoma, de forma secuencial, a los dibujos CAD abiertos y espera tanto la recepción como el término antes de cambiar de plano. Cada transición vuelve a adquirir el documento activo, espera que la pila de comandos quede ociosa y reintenta los rechazos COM transitorios sin duplicar la orden. Por seguridad no ejecuta si detecta varias instancias o versiones de AutoCAD/ZWCAD abiertas. El glosario visible incluye `BV`, `DL2`, `P0`, `PURGEALL`, `SETUP-A1`, `ST0`/`STO`, `W08`, `ZE`, `PLOTYA`, `VPTOGGLE` y `LAYORIGIN`. `VPTOGGLE` alterna la visibilidad de la capa `Viewport layer` y no requiere respuestas posteriores. También puedes escribir un comando nativo, como `_QSAVE`, si confirmas que termina por sí solo y no solicita puntos, opciones ni respuestas. El campo acepta únicamente el nombre del comando, sin parámetros ni expresiones LISP. Usa Cancelar si necesitas detener el recorrido. Para carpetas grandes, prefiere el procesamiento desde CMD, que aísla cada DWG mediante el motor elegido en Diagnóstico.

### Limpiar escalas sin uso

`PURGEALL` elimina también las escalas no utilizadas mediante
`-SCALELISTEDIT` → `Delete` → `*`, sin restablecer la lista predeterminada.
El CAD conserva la escala actual y las referenciadas por objetos anotativos.
Se aplica tanto al LISP/Comandos en vivo como al procesamiento por lotes.
El LISP no guarda automáticamente; los scripts por lotes sí guardan el DWG.
Guarda una copia antes de limpiar.

### Corregir el origen del papel conservando Layout

`LAYORIGIN` corrige el origen interno del papel de la presentación actual cuando
el área de trazado está en **Layout**. Restablece los campos DXF 148/149 a cero,
sin mover entidades ni modificar papel, escala, PC3, UCS o desplazamiento de
trazado. No guarda el DWG y permite deshacer con `U`. Activa el layout afectado,
ejecuta el comando y verifica la vista previa antes de guardar. Para un solo
dibujo úsalo directamente en CAD; Comandos en vivo lo envía a cada dibujo abierto.
Validado en AutoCAD 2025; pendiente de prueba en ZWCAD.

### Procesamiento DWG desde CMD

Pulsa **Preparar integración CAD** después de instalar o actualizar SINCAL y abre una ventana CMD nueva. En la carpeta del proyecto —puedes escribir `cmd` en la barra de direcciones del Explorador— ejecuta `AUDIT`, `ZE`, `PURGEALL`, `BV`, `DL2`, `PAGESETUP-A1` o `PUBLISH-A1`. Los lanzadores usan Windows PowerShell 5.1, incluido en Windows, y localizan el motor elegido mediante `%LOCALAPPDATA%\SINCAL\runtime\cad_engine.json`.

Con AutoCAD, SINCAL usa `accoreconsole.exe`. Con ZWCAD 2025/2026, crea una instancia COM aislada con `Visible = false`, abre cada plano, ejecuta el SCR, espera una señal de término, guarda, cierra y finaliza el proceso. Debes seleccionar **ZWCAD** en Diagnóstico, pulsar **Usar este motor** y volver a preparar la integración. ZWCAD debe estar instalado, activado y completamente cerrado antes de iniciar el lote; su automatización consume una licencia normal aunque no muestre interfaz. El lote se detiene si detecta una sesión ZWCAD abierta para no interferir con dibujos de trabajo. Conserva respaldos: estos comandos guardan cambios en todos los DWG de la carpeta.

### Conversión DXF

**Conversión DXF** es un módulo independiente: usa **Seleccionar DXF** para ver y escoger los archivos antes de cargarlos, o **Cargar carpeta** para listar todos los DXF de una ubicación. Marca solamente los deseados y conviértelos a DWG mediante una instancia CAD temporal. Cierra AutoCAD/ZWCAD antes de iniciarlo, conserva un respaldo y revisa los resultados en la consola Workbench.

### Proyecto y Consulta

El módulo **Proyecto** agrupa **Consulta**, **Generador de armadura** y **Sesiones**. Consulta es la única puerta de entrada del JSON: muestra todos sus campos desde el resumen general hasta estribos, cepas, tableros, materiales, planos y metadatos. OT, Revisión y Nombre de estructura se completan manualmente y se guardan de manera local, sin modificar el JSON. Las dimensiones conservan el valor original en milímetros y agregan su conversión a metros; las coordenadas se identifican como PTL y no se transfieren al módulo Ubicación. La consulta puede exportarse exclusivamente como `.txt`.

SINCAL recuerda la última ruta y solicita confirmación para reabrirla al iniciar. Si una sesión contiene cambios, cargar o limpiar otro proyecto exige guardarlos o descartarlos primero. El contexto activo alimenta automáticamente al Generador de armadura y también queda registrado dentro de las sesiones.

### Estratigrafía: informes CDI

El módulo reconoce los informes independientes de sondajes CDI, incluidos los
formatos S-1 y S-2 de Enlace Ruta 29. Se extraen por separado los horizontes, las
pasadas de perforación/recuperación (m y %), la presión (PSI) y los ensayos NSPT.
La longitud de muestra en cm no se confunde con la recuperación; los rechazos R
y la numeración original se conservan. Las discrepancias generan avisos sin
recalcular ni sustituir cifras oficiales. No se extrapolan estratos ni se estiman
valores desde las figuras. La empresa aparece solo como información de consulta
en pantalla, nunca como parte del dibujo CAD.

La vista previa y la inserción mantienen profundidades reales, textos RomanD
anotativos de 2,5 mm y la escala anotativa activa. Antes de insertar se debe
cotejar la extracción y la asignación de hatch con el informe original.

### Prospecciones

**Proyecto → Prospecciones** carga localmente un informe PDF con texto o imágenes, o un TXT
UTF-8 con tablas de estratos (N°, Inicio/Desde, Final/Hasta, Vs). Lista los arreglos
reconocidos, sus páginas y el Vs,30 oficial; permite escoger uno, consultar su tabla
y texto de origen, previsualizarlo e insertarlo en el dibujo CAD activo.
PaddleOCR transcribe las tablas en imágenes como respaldo del texto nativo. El motor
CPU y sus modelos vienen incluidos: no necesitas Python, una cuenta ni un servicio
OCR externo. Los informes se procesan localmente, con progreso y cancelación.
La búsqueda automática prioriza páginas con contexto Vs; en informes mixtos,
**OCR en todas las páginas** incluye también anexos escaneados sin ese contexto y
es más lento. Los informes completamente escaneados se examinan por OCR igualmente.
Las tablas deben tener columnas de estrato, inicio, final y Vs. Los bloques ambiguos
se señalan y no se envían a CAD; no se estiman magnitudes desde la curva.

**Ver original / texto** muestra la imagen y la confianza de las celdas. Las cifras
con confianza menor al 98 % quedan señaladas, pero una puntuación alta tampoco
garantiza exactitud. Todos los perfiles OCR requieren marcar **He cotejado las cifras
OCR con la imagen original** antes de insertarlos. Las sesiones conservan la imagen,
las coordenadas/confianzas y ese estado de revisión, además de los valores oficiales.
La identidad incluye sección y estructura cuando están documentadas; los rótulos
contradictorios se conservan con un aviso. No se unen perfiles solo por su nombre.
Verificado con las tablas nativas de Calera de Tango y los diez perfiles del anexo
P33 del IMS de Loreto, incluyendo nueve tablas en imagen.

Los valores son de solo lectura. El control de Vs,30 únicamente genera avisos
(tolerancia de 1 m/s o 0,5 % por redondeos); nunca reemplaza el valor publicado.
Se comparan también los resúmenes reconocidos y se pueden copiar los avisos
con sus páginas y la huella SHA-256 del documento. El resumen del arreglo 1-2 de
Calera de Tango difiere de su tabla individual y se informa como discrepancia.

**Guardar sesión** conserva tablas, valores oficiales, texto extraído, referencias,
selección y opción de incluir la tabla en CAD; no necesita el PDF original para
reabrir esos datos. Las sesiones anteriores se abren con Prospecciones vacío.
Cargar otro proyecto o iniciar una sesión nueva limpia las prospecciones anteriores.

Para insertar, activa Model en un dibujo en metros (`INSUNITS=6`) con el estilo
`RomanD` del master SINCAL y la escala anotativa deseada. Selecciona el punto en CAD.
Se crean líneas, círculos y textos editables, agrupados: cuadrícula ACI 8,
textos RomanD anotativos ACI 3, perfil escalonado ACI 5 y círculos/ticks ACI 1.
La cuadrícula ocupa 100 × 150 mm de papel y el texto 2,5 mm a la escala actual;
la tabla es opcional. El dibujo no se guarda automáticamente. La vista previa usa
una fuente de pantalla; la rotulación final en CAD usa RomanD.

### Pasarela BIM (módulo opcional)

El menú muestra **Pasarela BIM** inmediatamente antes de **Generador de armadura**,
tanto en la interfaz clásica como en la interfaz de escritorio web. Cuando falta
el módulo, el menú indica **No instalado** y su página ofrece
**Instalar Pasarela BIM**. Ese botón descarga e instala el paquete oficial
correspondiente a la versión de SINCAL instalada; su disponibilidad se comprueba
al solicitar la instalación. Después aparece **Abrir editor**. Si hay un módulo
anterior que no admite la integración, se ofrece **Actualizar Pasarela BIM**.
En la interfaz de escritorio, el editor se muestra dentro del panel central de
SINCAL. El proyecto, la selección y el historial se conservan al visitar otros
módulos y regresar. El motor sigue funcionando en un proceso independiente y
sólo se carga cuando se abre el editor. La interfaz clásica y el lanzador
independiente conservan su apertura en navegador.

El instalador general ofrece el componente **desmarcado por defecto**. También
puede añadirse después mediante el botón de instalación en línea. Si ya tienes
el paquete, despliega **Instalar o actualizar desde un ZIP local** y selecciona
`SINCAL_Pasarela_v0.3.2.zip`, o ejecuta el complemento independiente
`Setup_SINCAL_Pasarela_v0.3.2.exe` de la misma publicación oficial.
No hace falta reinstalar el programa general.
FreeCAD se instala por separado y sólo es necesario para generar el modelo.
La consulta del módulo indica si está disponible.

La instalación posterior se guarda en `%LOCALAPPDATA%\SINCAL\modules\pasarela-bim`;
el componente del instalador general, en `{app}\modules\pasarela-bim`.
La instalación por usuario tiene prioridad. Los resultados se guardan aparte,
en `%LOCALAPPDATA%\SINCAL\pasarela-bim\generados`; los proyectos se intercambian
mediante JSON en metros. Antes de actualizar, guarda ese JSON y pulsa
**Cerrar módulo** en SINCAL. Cerrar sólo la pestaña no detiene el servidor del editor.

La descarga comprueba el tamaño y SHA-256 publicados para el ZIP. Antes de
instalarlo también se validan identidad, versión de contrato, rutas y SHA-256
de cada archivo. La sustitución conserva la instalación anterior si falla.
El módulo tiene su propia versión, `0.3.2`, y no incluye FreeCAD ni OCR.
Las instrucciones de compilación independiente y distribución están en
[`packaging/windows/pasarela-bim/README.md`](packaging/windows/pasarela-bim/README.md).

### Generador de armadura

Prepara vistas, despieces y cubicación de fierro mediante comandos temporales enviados al CAD abierto:

- Estribos: separa **Estribo de entrada** y **Estribo de salida**, cada uno con su propio set de marcas, moldajes confirmados y cálculo. Cada estribo es una página continua: primero dimensiones y configuración; después revisión y marcas; finalmente despiece. El índice contextual permite saltar entre esas secciones. La zapata calcula las marcas 1–6, el suple 3-A opcional, empalmes 1–2/4–5 y las variantes excepcionales 2-A/5-A. Los diámetros se eligen desde una lista y los espaciamientos, origen de distribución, marcas y ganchos se editan únicamente en **Revisión y marcas**. La detección vigente usa `FR_ZAP`, `AA_ZAP`, `BB_ZAP`, `CC_ZAP` y `FF_ZAP`, conserva sus vértices y exige `INSUNITS = 6`.
- Travesaños: extremos, cuadrantes sobre tope, macizos y viga; geometría y despiece.
- Proyecto activo: recibe automáticamente desde **Proyecto → Consulta** los parámetros compatibles y los convierte a las unidades de la interfaz.

Las vistas de zapata generan cotas coordinadas con `MARK`, `GSG_COTAS` y `GSG_MLEADER`. El **despiece general de zapata** se inserta en Model, agrupa los empalmes, acota parciales con `GSG_ARM-COTAS` y describe cada pieza con RomanD a 2,5 mm de papel. Cada grupo queda identificado de manera independiente; cuando sus parámetros cambian, AutoCAD/ZWCAD permite actualizarlo, conservarlo, aceptar todos los cambios o cancelar desde la línea de comandos.

La pestaña **Asistente** construye desde el JSON el árbol completo de estribos, cepas, vigas, travesaños y losas. **Preparar dibujo** crea únicamente las capas de moldaje faltantes; **Analizar moldajes** usa el nombre de capa para reconocer la vista y, cuando se analiza un elemento concreto, solicita una selección por ventana para identificar su instancia. Los casos inequívocos avanzan automáticamente y los ausentes, duplicados, curvos o con unidades incorrectas quedan señalados para revisión. La zapata conserva su generador automático; las demás familias muestran las recetas previstas mientras se aprueban sus criterios estructurales.

Las sesiones guardan en un único archivo el estado editable del puente: JSON e instantánea verificable, ambos estribos, travesaños, reglas, marcas calculadas, pestaña activa y avance de vistas/despiece. **Abrir sesión**, **Guardar sesión** y **Nueva sesión** están bajo el título del generador; la biblioteca **Sesiones** permite buscar, ordenar y cargar proyectos anteriores. Los archivos formales se almacenan en `Documentos\SINCAL\Sesiones`; la recuperación automática se mantiene separada en `%LOCALAPPDATA%\SINCAL\sessions`. Los handles de moldaje se conservan sólo como referencia y siempre deben detectarse y confirmarse nuevamente en el DWG activo.

Los apartados **Muros**, **Consolas**, **Topes**, **Pilotes**, **Contrafuerte**, **Cepas**, **Vigas** y **Losa** ya forman parte del catálogo del asistente. Su reconocimiento de moldajes está disponible, mientras que la generación geométrica se habilitará receta por receta. Consulta **Documentación → Generador de armadura** para el glosario de capas, lectura de vistas y flujo de revisión. Verifica siempre dimensiones en cm, diámetros en mm y esviaje en grados.

### Módulo de ubicación

Lee puntos desde un KMZ de Google Earth, permite escoger un mapa MOP calibrado y genera un PNG con la posición marcada. El flujo es:

1. Cargar KMZ.
2. Seleccionar el Placemark.
3. Elegir la región correspondiente.
4. Aplicar microajuste opcional en píxeles.
5. Generar y guardar el croquis.

La primera utilización de una región solicita descargar su mapa y lo valida antes de guardarlo localmente.

### Registros del procesamiento por CMD

Cada ejecución de `AUDIT`, `ZE`, `PURGEALL`, `BV`, `DL2`, `PAGESETUP-A1` o
`PUBLISH-A1` crea **un solo `.log` para todo el lote** en
`%LOCALAPPDATA%\SINCAL\logs\scripts`. La consola muestra su ruta al comenzar y
al terminar. Puedes pegar esa carpeta en el Explorador y abrir el registro más
reciente con el Bloc de notas.

El registro contiene comando, carpeta, motor/version CAD, cada DWG, duración,
salida normal y de error de AutoCAD Core Console, código de salida, fallos y
resumen. ZWCAD conserva el diagnóstico de automatización COM, no su consola
interna. «Proceso terminado» no certifica que el dibujo esté libre de corrupción
ni sustituye la comprobación de los cambios esperados. Si se interrumpe Windows
o se fuerza el cierre, puede quedar un registro parcial sin resumen.

Al iniciar otra ejecución se eliminan únicamente registros propios de más de
**30 días** o los más antiguos que excedan **100 ejecuciones** (exceptuando los
asociados a procesos todavía activos). La salida detallada de CAD se limita a
5 millones de caracteres por ejecución, con aviso de truncamiento; los estados
y errores del lanzador siguen registrándose. No se borran DWG, respaldos ni
archivos ajenos. Para conservar una evidencia, copia el `.log` fuera de esa
carpeta antes de que expire. Los registros permanecen locales; pueden contener
rutas y nombres de proyectos, así que revísalos antes de compartirlos.

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

## Compilar una release de escritorio web

```powershell
python -m pip install -r requirements-build.txt
python -m pip install -r requirements-desktop-web.txt
pwsh -NoProfile -File tools/build_release.ps1 -DesktopWeb
```

El proceso valida código y pruebas, compila y firma el plugin y la aplicación,
y construye Pasarela BIM como ejecutable y paquete independientes. Firma el
ejecutable del módulo antes de calcular sus hashes, compila y firma ambos
instaladores y genera el manifiesto de release y `SHA256SUMS.txt`.
Los artefactos de `v3.0.28` quedan en `installer_output/v3.0.28/`.
Reserva una versión nueva y prepara un checkout de compilación aislado antes
de ejecutar el pipeline: volver a compilar la misma versión sustituye sus
artefactos locales. Para una compilación local no publicable puede usarse
`-SkipSigning`. `-SkipPasarelaModule` omite el paquete y la opción del módulo;
no debe usarse para esta release que incorpora Pasarela BIM.

La compilación utiliza CPython 3.12 x64 de python.org. `tools/build_ocr_runtime.py`
prepara un runtime aislado en `ocr_runtime/`, con dependencias fijadas en
`requirements-ocr-lock.txt` y modelos comprobados por SHA-256. Se incluye dentro del
paquete de aplicación (aumenta su tamaño); no se descarga nada al leer un informe.
Los avisos y licencias de terceros acompañan al runtime. No se incorpora PyMuPDF.
Para probar el PDF completo localmente: define `SINCAL_TEST_LORETO` con su ruta y
ejecuta `python -m pytest tests/test_prospecciones_ocr.py -q` después de preparar el runtime.

En la release pública deben adjuntarse juntos:

- `Setup_SINCAL_v3.0.28.exe`
- `SINCAL_App_v3.0.28.zip`
- `SINCAL_AutoCAD_v3.0.28.zip`
- `SINCAL_Pasarela_v0.3.2.zip`
- `Setup_SINCAL_Pasarela_v0.3.2.exe`
- `release-manifest_v3.0.28.json`
- `SHA256SUMS.txt`

No renombres ni vuelvas a firmar los paquetes después de calcular sus hashes:
el instalador y la instalación posterior del módulo usan las URLs y hashes de
esa release. Publica únicamente los siete artefactos anteriores; las carpetas
de preparación, registros y `pasarela-module-build.json` son salidas internas.

## Seguridad y diagnóstico

### Editor independiente de DWGPROPS

#### Nueva revisión de viñetas

- Abre **Nueva revisión**, debajo del editor DWGPROPS, y selecciona uno o varios DWG locales. Los archivos no se envían a Internet.
- Requiere un único layout y una única inserción de viñeta dinámica compatible, con tabla de seis columnas: revisión, fecha, dibujante, revisor, aprobador y descripción. Se admite la familia de tabla inspeccionada en VIÑETA G130; los formatos ambiguos o historiales distintos entre variantes se rechazan sin sobrescribir.
- Escribe la nueva revisión manualmente y completa los seis datos. Revisa las tablas de antes/después y confirma la lista de archivos.
- Conserva la cantidad de filas, dimensiones y expresiones FIELD de la primera fila. Congela la revisión vigente como valores fijos antes de desplazarla al historial. Las variantes internas compatibles se mantienen coherentes.
- La última fila sale del cuadro visible, pero se conserva en el respaldo completo del DWG anterior y se registra en el historial de ejecución. Los archivos originales se reemplazan solo después de verificar la copia guardada.
- No renombra el archivo, no modifica Fecha_Inf ni otras propiedades ajenas. Si la revisión ya coincide, el plano cambió desde la lectura, está bloqueado o el texto no cabe sin agrandar el cuadro, se omite y se informa. Cancelar termina entre archivos, sin revertir los ya guardados.
- Prueba nativa optativa: define `SINCAL_TEST_REVISION_DWG` con un DWG de ejemplo y ejecuta `python -m pytest tests/test_revisions.py -q`. Solo se modifican copias temporales, nunca el ejemplo original.

#### Edición de propiedades

- Abre **Editor DWGPROPS**, selecciona una carpeta y espera la lectura de sus DWG (sin subcarpetas, hasta 500 archivos).
- Requiere Windows y AutoCAD 2025 o 2027 con Core Console y el conector DWGPROPS correspondiente. El selector permite elegir la versión disponible; no usa COM, los dibujos abiertos del usuario ni ZWCAD.
- Selecciona un archivo para editarlo individualmente o varios para aplicar cambios comunes. El buscador y **Seleccionar visibles** permiten preparar un lote específico.
- Los valores diferentes se indican como tales. Solo las propiedades marcadas se modifican; un valor vacío no equivale a eliminar. Puedes crear propiedades o marcar su eliminación.
- Confirma la lista de planos y cambios antes de guardar. Se edita una copia temporal, se reabre para verificarla y se crea un respaldo en `SINCAL_Backups/<ejecución>` junto al original antes de reemplazarlo.
- Si el original cambió desde la lectura, está abierto/bloqueado o falla CAD, el archivo no se reemplaza. Los resultados son por archivo; no se revierte automáticamente un lote parcialmente completado.
- Se reutiliza un único Core Console por lote, procesando las copias temporales secuencialmente. Se cierra al terminar, cancelar o fallar; no interviene en AutoCAD abierto por el usuario.
- Los archivos cuyos valores ya coinciden se muestran como **Sin cambios**: se verifica que el original siga intacto, pero no se inicia CAD ni se crea un respaldo o se reescribe ese DWG innecesariamente.
- Cancelar se atiende entre dibujos. El conector reabre cada archivo guardado, comprueba propiedades, formato DWG e inventario de entidades y señala que cerró las bases de datos. Un timeout anterior a esa confirmación nunca reemplaza el original. Los registros se consultan en el historial de ejecuciones de Home.
- Las propiedades estándar de DWGPROPS y las propiedades personalizadas no marcadas se conservan. La actualización visual de los FIELD depende de la evaluación de campos del propio DWG al abrir o regenerar.
- Prueba nativa optativa (usa únicamente copias temporales de fixtures del repositorio): define `SINCAL_TEST_NATIVE_DWGPROPS=1` y ejecuta `python -m pytest tests/test_dwgprops_native.py -q`. Requiere conectores compilados y firmados en `src/Sincal.DwgProps/bin/2025` y `2027`. La compilación del instalador los firma e incluye automáticamente.

El repositorio de desarrollo puede ser privado. El canal público contiene únicamente recursos autorizados y binarios de release; no recibe fuentes Python/.NET ni secretos. Protege `main`, limita el acceso de escritura y conserva la revisión de los LISPs y scripts, ya que son código ejecutable.

Los registros locales están en `%LOCALAPPDATA%\SINCAL\logs\sincal.log` y los incidentes estructurados en `%LOCALAPPDATA%\SINCAL\diagnostics\incidents.jsonl`. Ninguno se transmite automáticamente. Si los comandos CAD no aparecen, actualiza recursos, ejecuta Diagnóstico, vuelve a preparar la integración y reinicia CAD. Si una descarga falla, revisa conexión, proxy y antivirus antes de reintentar.
