# SINCAL Suite — Ingeniería y estándares CAD

**SINCAL Suite** es una aplicación para Windows que centraliza estándares de dibujo para AutoCAD/ZWCAD, automatiza el procesamiento de planos y entrega herramientas de apoyo para ingeniería estructural y ubicación geográfica. La versión de producto es 3.0. Esta guía corresponde a la release `v3.0.43`, con interfaz de escritorio web y Pasarela BIM como módulo opcional.

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
`packaging/windows/SINCAL_Web.spec`. La release `v3.0.43` se construye con
`tools/build_release.ps1`; la interfaz web es la opción predeterminada.
`-DesktopWeb` se conserva como parámetro compatible. El pipeline rechaza el
arranque Tk y verifica el contenido real del EXE antes de firmarlo.
La versión instalada sólo cambia al ejecutar su instalador.

Cada publicación debe identificar sus pruebas y limitaciones. Antes de publicarla
se comprueban el ejecutable empaquetado, WebView2, los paquetes firmados y las
operaciones modificadas sobre archivos de ensayo. El documento
[Estado de la migración](docs/MIGRACION_WEB.md) conserva antecedentes técnicos;
sus pendientes históricos no sustituyen el resultado de verificación de cada release.

## Instalación web y distribución

SINCAL Suite se distribuye mediante un instalador web firmado. El archivo
`Setup_SINCAL_v3.0.43.exe` descarga desde su release pública los paquetes exactos
de la aplicación y del plugin AutoCAD, comprueba sus SHA-256 y después los instala.
El componente **Pasarela BIM** aparece **desmarcado por defecto**: su paquete
independiente sólo se descarga si se selecciona. También puede instalarse más adelante.

El programa base no incorpora los 125 MB de mapas regionales. El paquete web sí contiene una copia inicial del master DWG, LISPs, startup, scripts, plumilla, calibración y ayuda estructural para que el primer arranque sea funcional. GitHub mantiene esos recursos al día mediante actualizaciones menores. Cada mapa regional se descarga solamente cuando se selecciona por primera vez en el módulo Ubicación.

Para instalar se necesita conexión a Internet y acceso HTTPS a `github.com` y `raw.githubusercontent.com`. Una vez descargados los componentes necesarios, las funciones instaladas continúan disponibles sin conexión.

## Primer inicio

1. Descarga y ejecuta el instalador de `v3.0.43` desde su publicación oficial, con SINCAL y CAD cerrados.
2. Abre SINCAL; la aplicación comprobará automáticamente si existe una actualización menor de recursos.
3. Abre **Diagnóstico**, verifica el motor CAD sugerido y cámbialo si necesitas otra versión.
4. Pulsa **Preparar integración CAD**.
5. Reinicia AutoCAD/ZWCAD una vez para activar el cargador y las rutas de confianza.
6. Abre **Documentación** para consultar el manual buscable de comandos y módulos.
7. Si necesitas Pasarela BIM y figura **No instalado**, abre su página y pulsa
   **Instalar Pasarela BIM**. Se descargará el módulo correspondiente a esta
   versión de SINCAL; al terminar podrás usar **Abrir editor**.

La versión 3.0.43 incluye las pestañas **Revisiones** y **Propiedades
personalizadas** para AutoCAD 2026/2027 (.NET 10) y ZWCAD 2026. Después de
preparar la integración y reiniciar CAD, selecciona la viñeta y pulsa
**Editar revisiones**, o ejecuta `REV-EDIT`. Para abrir directamente las
propiedades, sin seleccionar una viñeta, ejecuta `PROPS-EDIT`.

En Propiedades, marca los nombres que quieres unificar, edita sus valores y
selecciona los dibujos abiertos de destino. Se crean las propiedades faltantes,
se conservan las no marcadas y se actualizan los Fields. Un valor vacío marcado
deja el contenido vacío. Aplicar opera sólo sobre la pestaña activa y no guarda
los dibujos. En ZWCAD, un destino inactivo puede necesitar `REGEN`; el editor
lo indica. Un solo `U` no garantiza revertir conjuntamente tabla y propiedades.

La copia base de los recursos esenciales queda junto a la aplicación. Las revisiones descargadas, estados, diagnósticos y registros se almacenan en `%LOCALAPPDATA%\SINCAL`: son datos internos de SINCAL que no necesitan acompañar el perfil móvil del usuario. La integración CAD activa se materializa en `%APPDATA%\Estandar SINCAL`: AutoCAD/ZWCAD deben poder encontrar allí LISPs, startup y scripts desde el perfil del usuario. No son dos copias equivalentes: **Local** es almacén y estado de la aplicación; **Roaming** es la copia operativa expuesta al CAD.

Al cerrar la ventana principal con **X**, SINCAL finaliza su proceso. La aplicación no se oculta en la bandeja ni permanece abierta en segundo plano.

## Componentes principales

### Home y Sincronizador

- Comprueba una nueva versión completa desde las Releases públicas.
- Revisa recursos al iniciar y cada minuto mediante un manifiesto liviano.
- Avisa en Home cuando hay recursos pendientes; la descarga se inicia con **Comprobar recursos** y **Aplicar actualización**. La revisión mostrada corresponde al commit de origen.
- Descarga LISPs, startup, scripts, CTB, master, tutoriales y mapas autorizados.
- Valida tipo, tamaño y SHA de Git antes de activar cada archivo.
- Comprueba una publicación sin reutilizar respuestas antiguas y descarga sus archivos desde una revisión fija. Si la publicación cambia antes de aplicar, solicita comprobar nuevamente.
- Detecta y repara archivos locales alterados o una preparación CAD interrumpida; reutiliza las copias verificadas y conserva los recursos locales cuando no hay conexión.
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

### Reactivar Fields de la revisión actual en ZWCAD

`ACTUALIZAR-VINETA` permite seleccionar una inserción `VIÑETA` / `VINETA` y
reactivar los Fields DWGPROPS deshabilitados de la primera fila de su tabla de
revisiones de seis columnas. Comprueba que las propiedades referidas existan y
conserva los códigos de los Fields, las opciones de evaluación ya activas y las
filas históricas. No cambia propiedades, no agrega una revisión ni guarda el plano.
Revisa el resultado y guarda si corresponde; `U` permite deshacer. El comando
actúa sobre la definición utilizada por la inserción seleccionada, por lo que
otras inserciones que compartan esa definición verán la misma corrección.
No recorre los demás bloques del dibujo ni modifica referencias externas.

Es una recuperación inmediata: en la prueba con ZWCAD 2026 actualiza G → H y
conserva historial, dimensiones y viewports, pero ese DWG vuelve a desactivar
los campos al guardar/reabrir. Puede ser necesario repetir el comando después
de otro cambio de DWGPROPS. No se considera una reparación permanente.

El conector nativo corrige la creación de nuevas revisiones: después de que CAD
materializa los Fields de la tabla, sus campos hijos heredan las opciones del
padre. Comprueba estas opciones también después de guardar y reabrir; una
evaluación forzada inicial no basta para aceptar el resultado.

Para cuadros existentes, el conector incorpora una operación interna de
mantenimiento `revisionFieldRepairTables`, sobre handles de tablas explícitos
y copias temporales. Sólo admite el patrón conocido de los cuatro Fields de la
revisión actual. Conserva DWGPROPS, historial, formato, dimensiones y viewports;
verifica el archivo guardado antes de aceptarlo. La tabla puede reconstruir los
identificadores internos de esos cuatro Fields, conservando sus expresiones y
vínculos. No añade controles a la interfaz ni modifica dibujos abiertos.
Esta corrección requiere distribuir el conector en una nueva release; sincronizar
únicamente los LISPs no actualiza el binario. Pruebas y protocolo en
[`tests/cad/REVISION_FIELDS.md`](tests/cad/REVISION_FIELDS.md).

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
`SINCAL_Pasarela_v0.3.3.zip`, o ejecuta el complemento independiente
`Setup_SINCAL_Pasarela_v0.3.3.exe` de la misma publicación oficial.
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
El módulo tiene su propia versión, `0.3.3`, y no incluye FreeCAD ni OCR.
Las instrucciones de compilación independiente y distribución están en
[`packaging/windows/pasarela-bim/README.md`](packaging/windows/pasarela-bim/README.md).

### Generador de armadura

La pantalla de parámetros de **Estribos** ocupa el ancho disponible y muestra el visor a la derecha, junto a las dimensiones y reglas de armadura. La vista se actualiza al editar y conserva giro, zoom y filtros. Las medidas editadas reconstruyen localmente el moldaje de zapata y su distribución de acero; el JSON original se conserva. Los valores incompletos o inválidos se señalan sin mostrar una armadura anterior como actual. **Calcular marcas** e **Insertar en CAD** siguen siendo acciones explícitas. En ventanas estrechas, los paneles se apilan.

El panel del visor reúne los controles de navegación y **Ampliar visor** en su cabecera; debajo del dibujo sólo muestra un estado breve y la ayuda de navegación. En el visor ampliado, los elementos y sus marcas aparecen a la izquierda del dibujo. Las marcas visibles se iluminan con el color de sus fierros; las ocultas se apagan. Los controles de moldaje y los avisos de datos/alcance están allí, con desplazamiento independiente para mantener visible el dibujo. Al cerrar, el panel conserva la cámara y los filtros elegidos. Se omiten la leyenda de familias y el párrafo largo de descripción del acero.

**Ampliar tabla de marcas** aprovecha el ancho de pantalla para mostrar sus doce columnas completas. Los textos largos se ajustan a varias líneas, sin ocultar valores. Si hay muchas filas, se desplazan dentro de la tabla y el botón de cierre permanece visible. Pulsar una marca sigue abriendo su despiece.

**Ampliar visor** abre la isométrica en una ventana ampliada dentro del programa; el asistente conserva **Abrir isométrica del estribo**. Ambos visores permiten girar el conjunto y acercar. El ampliado incorpora los controles para resaltar u ocultar elementos y atenuar los moldajes. Su navegación sigue la del visor de Cadence: **botón central para desplazar**, **Mayús + botón central para orbitar** y **rueda para acercar o alejar hacia el cursor**. El eje Z permanece vertical y la escala se conserva al orbitar u ocultar elementos. Seleccionar un elemento centra la órbita en él; **Ajustar** encuadra la geometría visible y **Isométrica** restablece la cámara. En pantalla táctil, un dedo desplaza y dos desplazan y acercan. Los perfiles nominales y las piezas sin datos suficientes se declaran en el visor. La zapata muestra todas las piezas de sus familias activadas: mallas, suples y laterales, con ganchos, radios 3Ø y empalmes. Cálculo, despiece, vistas CAD e isométrica comparten el mismo modelo físico. Las piezas empalmadas se colocan lado a lado, en contacto según sus diámetros reales, manteniendo el traslapo y los recubrimientos. El visor y el ajuste de empalmes muestran esas posiciones físicas; el despiece conserva las formas y largos de cada pieza. Los ganchos de las mallas son verticales a 90°; los laterales siguen el contorno en planta y sus ángulos de esviaje. Las cotas de corte se redondean hacia arriba al centímetro, sin alargar ni deformar la geometría: el modelo conserva también el desarrollo exacto. Los recubrimientos se verifican hasta la superficie de cada fierro; un gancho incompatible genera un aviso y no se recorta. Las armaduras de los demás elementos siguen pendientes. La navegación y los filtros del visor no consultan CAD ni modifican cantidades o marcas; sólo la eliminación explícita de una pieza modifica el cálculo. La elección de navegación por elemento o por corte continúa abierta.

Los laterales se colocan por fuera de las patas verticales de las mallas, conservando el recubrimiento a su superficie. Las patas se ajustan hacia adentro según los diámetros y el reparto lateral empieza en la tangencia del doblez superior; el origen inverso empieza abajo. La malla X queda por fuera de la Y en las caras superior e inferior, conservando esa jerarquía al cambiar de corte. Las vistas de la zapata no muestran cotas de empalme; el despiece y la vista previa de ajuste sí las conservan.

La orientación de la malla longitudinal se decide automáticamente por la magnitud del esviaje. Con menos de 10° (incluidos los valores decimales entre 9° y 10°), sus fierros y suples siguen las caras laterales de la fundación y tienen largos constantes. Desde 10°, la malla es perpendicular y recorre la proyección útil completa, incluidas las cuñas de ambos extremos, con largos variables. Los signos positivo y negativo orientan la geometría sin cambiar el criterio. La malla transversal conserva su dirección y la separación se mide en la dirección transversal de reparto existente. Cálculo, planta E–E e isométrica comparten sus ejes de reparto. Los largos variables se agrupan bajo una misma marca: la tabla conserva su cantidad total y el despiece muestra `VAR`, el rango y el listado de largos desarrollados con sus cantidades. El dibujo de despiece representa la pieza de mayor longitud, no una longitud única para toda la serie. Longitud total y peso suman las variantes reales; las cantidades no dependen de la vista visible. Una serie que requiera empalmes aún no definidos se detiene con un mensaje explícito.

En CAD, los círculos transversales se presentan tangentes a la línea fina del longitudinal; esta convención no desplaza los ejes físicos del despiece ni de la isométrica. El reparto rectangular y los laterales fijan sus dos extremos en las tangencias de los dobleces. El cierre conserva el paso nominal, añade el extremo antes omitido y, si el residuo es menor que el diámetro, divide por igual el último intervalo completo y ese residuo para no superponer barras. Las cantidades incorporan esas piezas reales. En el borde esviado, la malla Y se ancla físicamente a las dos tangencias del fierro X representativo de la vista frontal. En la malla perpendicular, el resto del reparto cubre ambas cuñas desde esos anclajes. Cuando los longitudinales siguen las caras laterales, sus ejes mantienen el amarre frontal y el giro indicado por el esviaje. Este amarre corresponde sólo a la sección mostrada, no a todas las tangencias de la arista inclinada. Una separación incompatible se informa sin recortar ni desplazar piezas arbitrariamente.

Un clic sobre un fierro de la isométrica lo resalta y permite **Eliminar este fierro**. Si coinciden varias piezas bajo el cursor, el selector permite escoger cuál; una pieza de empalme se elimina por separado de su continuación. Se recalculan la cantidad, las variantes de largo y el peso de su marca, sin renumerar las demás. **Deshacer eliminación** recupera la última baja de la sesión; la lista de eliminados del visor ampliado permite restaurarlas después de guardar y reabrir el proyecto. Entrada y salida guardan sus propias bajas. Si un cambio de parámetros altera la identidad geométrica de una pieza eliminada, el cálculo pide revisar esa baja antes de insertar para no aplicarla a otro fierro. Las vistas del DWG ya insertadas se actualizan al regenerarlas expresamente; seleccionar, filtrar o eliminar en el visor no contacta AutoCAD.

B–B y C–C siguen la cara lateral esviada: su rectángulo mide `largo / cos(esviaje)` por el alto, mientras A–A conserva el largo perpendicular. Con 7,50 m y 12°, B–B/C–C miden 7,668 m. Sólo en el plano CAD, estos dos cortes muestran un longitudinal representativo de recubrimiento a recubrimiento, conservando ganchos y radios. Esta representación no cambia los fierros fabricados: la isométrica conserva su orientación y geometría reales, y tabla, peso, despiece y marcas se obtienen del modelo físico. Las bajas individuales siguen vigentes y no se reemplaza una pieza eliminada por una vecina. Las referencias se validan como antes; el dibujo representativo no permite estirar una selección incompatible. Las ubicaciones independientes de B/C en planta siguen pendientes y conservan por ahora la estación representativa central.

La vista previa de cada marca reproduce la tipografía y proporciones de **GSG_COTAS** del master, con textos, líneas de cota, auxiliares y flechas en blanco. Usa la fuente RomanD instalada con CAD. Las cotas se expresan en cm y los ángulos muestran la abertura interior real entre tramos cuando el doblez deja de ser recto; el detalle del ángulo también informa el giro de doblado. Las series rotulan la parcial cambiante como **VAR. L= mínimo - máximo**, descontando los ganchos fijos del rango total. Por ejemplo, largos totales de 221–946 cm con dos ganchos de 100 cm corresponden a una parcial variable de 21–746 cm. Esta presentación no modifica la geometría, cantidades, marcas ni la inserción CAD.

Prepara vistas, despieces y cubicación de fierro mediante comandos temporales enviados al CAD abierto:

- Estribos: separa **Estribo de entrada** y **Estribo de salida**, con dimensiones, reglas y marcas propias. Primero se carga el JSON, se revisan los parámetros y se calcula la zapata. Después se usa un botón por vista: frontal, A–A, B–B, C–C o planta E–E. La zapata conserva las marcas y reglas ya definidas; las otras familias requieren definiciones del usuario.
- Travesaños: extremos, cuadrantes sobre tope, macizos y viga; geometría y despiece.
- Proyecto activo: recibe automáticamente desde **Proyecto → Consulta** los parámetros compatibles y los convierte a las unidades de la interfaz.

Todos los elementos, vistas y despieces de un **estribo completo** comparten una tabla nativa de `MARCA-SC`: A = marca, B = cantidad total de piezas de esa marca en el estribo, C = diámetro en mm, D = separación en cm. La primera inserción solicita seleccionar una tabla compatible o crearla en un punto indicado; después se reutiliza la asociación de esa instancia (entrada o salida). Cada elemento sólo actualiza sus propias filas: recalcular la zapata conserva las de muros, alas, topes y otros elementos, además de las filas manuales ajenas al cálculo. Los identificadores permanecen estables y las marcas son únicas en toda la tabla, también entre elementos. Las marcas usan el formato `3A`; los proyectos anteriores con `3-A` se migran al leerlos. Sólo la zapata dispone actualmente de reglas de armadura definidas.

Las tablas nuevas toman el prototipo `TABLA-FIERROS` del master, con estilo `SINCAL - Tabla`, capa `SINCAL - Tablas`, fuente romans y encabezados `MARCA | # | Ø | @`. Se eliminan las filas de ejemplo y se ajusta el formato a la escala anotativa real: a 1:75 en metros, el ancho es 6, las filas miden 0,375 y el texto 0,18 (2,4 mm en papel). Al reutilizar una tabla antigua que coincida exactamente con la firma genérica del generador, se corrige su formato dentro de la misma operación, sin reemplazar el objeto ni sus identidades de fila. Las tablas administradas por el generador reaplican el formato después de escribir las marcas, para que las filas nuevas no hereden tamaños y márgenes desproporcionados. Las tablas manuales conservan su presentación.

Las vistas insertan `SINCAL_MARCA_SC_V3`, con campos vinculados a la tabla y estados superior/inferior/suple. Usan los estados sin cantidad porque cada vista puede representar sólo una cara y B contiene el total de esa marca. Las cotas geométricas conservan `GSG_COTAS`; las directrices se asocian al bloque nativo. El despiece acota parciales con `GSG_ARM-COTAS` e inserta `SINCAL_MARCA_DE_V2` directamente en Model, fuera de los bloques de geometría, para mantener editables sus atributos y propiedades dinámicas. El cálculo inicializa cantidad total y largo en cm; las actualizaciones ordinarias de `MARCA-DE` conservan esos atributos manuales. Cuando cambia un grupo de despiece, se puede actualizar, conservar, aceptar todos los cambios o cancelar; aceptar su regeneración aplica los nuevos valores calculados. La geometría de otras vistas requiere regenerar su botón cuando cambia el cálculo: actualizar campos de una tabla no recalcula el dibujo por sí solo.

La entrega del estribo se divide mediante **dos copias completas del DWG**, usando Guardar como y ocultando las vistas que no correspondan. El primer archivo muestra frontal, A–A, B–B y C–C; el segundo muestra D–D, E–E y la armadura de los topes sísmicos. Ambos conservan toda la información, la tabla completa y los vínculos locales de los bloques. La visibilidad no interviene en las cantidades ni en las marcas. No se exportan sólo entidades seleccionadas ni se eliminan las vistas ocultas. Las dos copias son independientes: no se ha implementado sincronización de cambios entre archivos. La conservación nativa de vínculos después de Guardar como debe comprobarse en CAD al validar la integración.

Para las siguientes etapas se acuerdan tablas independientes por plano: una para cepa (una por cada cepa cuando haya varias distintas), otra para viga, otra para travesaños y otra para losa. Cada tabla conserva sus propios vínculos y cantidades; actualizar una estructura no modifica las tablas de las otras. Este alcance está registrado para el desarrollo posterior y no implica que sus reglas de armadura ya estén implementadas.

El generador ya no utiliza el bloque antiguo `MARK`, MText separado ni textos de marca en las cotas. Los recursos y comandos de marcaje usados por otros módulos se conservan. La implementación cuenta con pruebas automatizadas; la comprobación visual de esta integración en AutoCAD/ZWCAD se debe realizar en una copia desechable antes de usarla en producción.

El **Asistente** construye desde el JSON el árbol de estribos, cepas, vigas, travesaños y losas. Actualmente cada orden de vista pide en CAD **únicamente los puntos de la zapata**, aunque el JSON incluya pilotes u otros elementos. Las vistas rectangulares usan dos esquinas opuestas: superior izquierda e inferior derecha. La planta esviada E–E pide tres esquinas consecutivas (superior izquierda, superior derecha e inferior derecha) y reconstruye la cuarta. Los puntos no son ventanas de selección de objetos. No se buscan moldajes por nombre de capa ni se recorre el dibujo para reconocerlos. Se incorporarán referencias de los demás elementos cuando sus armaduras e inserción estén implementadas.

Las coordenadas CAD se interpretan explícitamente en metros, centímetros o milímetros. El modo automático usa la declaración del dibujo, pero las dimensiones y el esviaje de la referencia se contrastan con el cálculo antes de insertar. La base superior debe estar horizontal; las plantas giradas se rechazan de forma explícita en esta versión. Si no coincide, se detiene el envío y se informan ambas medidas. Una elección explícita de unidades no modifica `INSUNITS`. Cancelar la secuencia no inserta armaduras.

El flujo web conserva las referencias devueltas por instancia y vista durante la sesión. Cada nueva inserción vuelve a pedir los puntos y verifica el dibujo de destino; no reutiliza handles ni detecciones de otro dibujo.

Los apartados **Muros**, **Consolas**, **Topes**, **Pilotes**, **Contrafuerte**, **Cepas**, **Vigas** y **Losa** forman parte del catálogo. Sus armaduras completas siguen pendientes de las reglas que debe definir el usuario. No se inventan diámetros, distribuciones ni recetas para completar esas familias. Los controles mantienen dimensiones en cm, diámetros en mm y esviaje en grados.

En **Ala izquierda/Ala derecha** están disponibles las **mallas exterior e interior** para cálculo y vista previa. Sus parámetros y bajas individuales se guardan por malla, ala y estribo, sin alterar la zapata ni el JSON importado. El perfil distingue el cuerpo apoyado y la aleta activada por el JSON: los verticales del cuerpo llegan al recubrimiento inferior de la zapata; los cortos de la aleta terminan en su diagonal. Los verticales tienen dos ganchos editables de 40 cm; los horizontales separan el gancho del ala (40 cm iniciales) y el del encuentro (ingreso explícito). Los horizontales bajos llegan al frontal y los altos al espaldar. Los radios son 3Ø; si una pieza supera 12 m o un gancho no cabe, se informa el problema sin inventar empalmes ni acortarlo.

El cálculo del ala exige diámetros, separaciones y recubrimientos propios y una revisión explícita de las cotas nominales. Sus piezas reales alimentan la isométrica, cantidades, pesos y despiece GSG_COTAS; las series variables mantienen una marca por grupo. Las marcas se reservan en el mismo estribo y no pueden coincidir entre mallas ni con las de la zapata u otra ala. Los verticales quedan junto a la cara de hormigón respectiva y los horizontales pegados hacia el centro del espesor; el reparto horizontal comienza sobre la zapata, en la base del muro. Cuando el ala está girada, el horizontal conserva el quiebre de la unión con el espaldar, su radio y su desarrollo real. La inserción CAD de estas mallas todavía no está habilitada; las órdenes existentes siguen solicitando únicamente la zapata.

La malla interior se activa dentro del mismo elemento. Al activarla por primera vez copia los parámetros exteriores, conservando marcas independientes; la copia posterior es explícita. Sus ganchos inferiores tienen la misma dirección que los exteriores sólo en los verticales anclados dentro de la zapata. En los cortos de aleta ambos ganchos vuelven hacia el espesor. Los horizontales interiores comparten la dirección del gancho frontal/espaldar con los exteriores, mientras el gancho libre del ala vuelve hacia el espesor. Desactivar la malla conserva sus datos, marcas y bajas para la siguiente activación; los proyectos anteriores mantienen únicamente la exterior.

Los suples verdes se intercalan en la malla interior: un grupo llega con su gancho al frontal y el superior al espaldar. El límite inferior del primero se edita sobre el perfil como una altura hacia abajo desde la coronación del frontal; los grupos comparten su encuentro y cierran con un salto máximo de 20 cm. Cada grupo tiene activación, diámetro, separación, marca, gancho y tramo hasta el extremo libre propios. Los antiguos rangos de axila no se aplican a esta distribución corregida.

Con aleta, el fierro de canto es obligatorio. Se ingresa cantidad, diámetro, marca y largo total, con gancho superior opcional (20 cm iniciales). Las piezas se reparten uniformemente entre recubrimientos y la prolongación resultante debe ser de al menos 100 cm. El programa no redondea el largo elegido ni acorta piezas para encajarlas; valida el recorrido completo contra el ala y la zapata. Los refuerzos comparten la tabla del estribo y conservan su identidad para eliminar y restaurar piezas individuales.

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
5. Espera que termine correctamente **Publicar recursos SINCAL**. El push al repositorio privado por sí solo todavía no actualiza el canal de distribución.
6. Con el sincronizador actualizado y conexión disponible, SINCAL detectará la publicación en el siguiente ciclo de comprobación y avisará para instalarla desde Home. La comprobación manual consulta la publicación disponible en ese momento.

Los cambios en Python, interfaz, plugin .NET o instalador requieren una release completa. Los recursos menores no reemplazan ejecutables.

La corrección del sincronizador también requiere distribuir una nueva release e instalarla una vez en cada equipo: los ejecutables anteriores no reciben esta lógica mediante los LISPs. Después, las nuevas revisiones de recursos se detectan y aplican desde Home sin copiar archivos ni corregir estados a mano. Estas mejoras corresponden al código actual del repositorio; no implican que una release nueva ya esté publicada.

## Compilar una release de escritorio web

```powershell
python -m pip install -r requirements-build.txt
python -m pip install -r requirements-desktop-web.txt
pwsh -NoProfile -File tools/build_release.ps1 -DesktopWeb
```

El proceso valida código y pruebas, compila los componentes que cambiaron y
reutiliza aplicación, conectores CAD, integración del Explorador y Pasarela BIM
cuando coinciden sus fuentes, herramientas y hashes de salida. Los archivos
faltantes o alterados invalidan su comprobante. Las firmas se verifican antes
de reutilizarlas. Genera los instaladores, el manifiesto y `SHA256SUMS.txt`.
Los artefactos de `v3.0.43` quedan en `installer_output/v3.0.43/`.
Reserva una versión nueva y usa un checkout de compilación aislado y estable:
conservar ese directorio permite reutilizar su caché. Volver a compilar la misma versión sustituye sus
artefactos locales. Para una compilación local no publicable puede usarse
`-SkipSigning`. `-SkipPasarelaModule` omite el paquete y la opción del módulo;
`-CleanBuild` fuerza reconstrucción y limpia la caché local de compilación;
por defecto se conservan `build/`, `dist/`, las salidas nativas y los paquetes
de módulos. Las pruebas de la release siguen ejecutándose.

La compilación utiliza CPython 3.12 x64 de python.org. El motor OCR se distribuye
como complemento independiente y **no se prepara, copia ni comprime en cada
release principal**. `python tools/build_ocr_module.py` construye su ZIP e
instalador en `installer_output/prospecciones-ocr/v1.0.0/`; admite
`--skip-runtime` para reutilizar el runtime existente tras validar fuentes y modelos.
Los artefactos idénticos se reutilizan comprobando sus hashes. El complemento
se instala por usuario y se detecta desde Prospecciones, sin cambiar su pantalla.
Las actualizaciones de SINCAL conservan el OCR de instalaciones anteriores.
`tools/build_ocr_runtime.py` prepara el runtime aislado con dependencias fijadas
en `requirements-ocr-lock.txt` y modelos comprobados por SHA-256.
No se descarga nada al leer un informe. Véase
[`packaging/windows/prospecciones-ocr/README.md`](packaging/windows/prospecciones-ocr/README.md).
Los avisos y licencias de terceros acompañan al runtime. No se incorpora PyMuPDF.
Para probar el PDF completo localmente: define `SINCAL_TEST_LORETO` con su ruta y
ejecuta `python -m pytest tests/test_prospecciones_ocr.py -q` después de preparar el runtime.

En la release pública deben adjuntarse juntos:

- `Setup_SINCAL_v3.0.43.exe`
- `SINCAL_App_v3.0.43.zip`
- `SINCAL_AutoCAD_v3.0.43.zip`
- `SINCAL_Pasarela_v0.3.3.zip`
- `Setup_SINCAL_Pasarela_v0.3.3.exe`
- `release-manifest_v3.0.43.json`
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
- Requiere Windows y AutoCAD 2025, 2026 o 2027 con Core Console. AutoCAD 2026 reutiliza el conector compatible de 2025; 2025 y 2027 conservan sus conectores propios. El selector permite elegir la versión disponible; no usa COM, los dibujos abiertos del usuario ni ZWCAD.
- Selecciona un archivo para editarlo individualmente o varios para aplicar cambios comunes. El buscador y **Seleccionar visibles** permiten preparar un lote específico.
- Los valores diferentes se indican como tales. Solo las propiedades marcadas se modifican; un valor vacío no equivale a eliminar. Puedes crear propiedades o marcar su eliminación.
- Confirma la lista de planos y cambios antes de guardar. Se edita una copia temporal, se reabre para verificarla y se crea un respaldo en `SINCAL_Backups/<ejecución>` junto al original antes de reemplazarlo.
- Si el original cambió desde la lectura, está abierto/bloqueado o falla CAD, el archivo no se reemplaza. Los resultados son por archivo; no se revierte automáticamente un lote parcialmente completado.
- Se reutiliza un único Core Console por lote, procesando las copias temporales secuencialmente. Se cierra al terminar, cancelar o fallar; no interviene en AutoCAD abierto por el usuario.
- Los archivos cuyos valores ya coinciden se muestran como **Sin cambios**: se verifica que el original siga intacto, pero no se inicia CAD ni se crea un respaldo o se reescribe ese DWG innecesariamente.
- Cancelar se atiende entre dibujos. El conector reabre cada archivo guardado, comprueba propiedades, formato DWG e inventario de entidades y señala que cerró las bases de datos. Un timeout anterior a esa confirmación nunca reemplaza el original. Los registros se consultan en el historial de ejecuciones de Home.
- Las propiedades estándar de DWGPROPS y las propiedades personalizadas no marcadas se conservan. La actualización visual de los FIELD depende de la evaluación de campos del propio DWG al abrir o regenerar.
- Prueba nativa optativa (usa únicamente copias temporales de fixtures del repositorio): define `SINCAL_TEST_NATIVE_DWGPROPS=1` y ejecuta `python -m pytest tests/test_dwgprops_native.py -q`. Requiere conectores compilados y firmados en `src/Sincal.DwgProps/bin/2025` y `2027`. La compilación del instalador los firma e incluye automáticamente. El SDK administrado de AutoCAD 2025 está admitido en AutoCAD 2026 según la [compatibilidad oficial de Autodesk](https://help.autodesk.com/cloudhelp/2026/ENU/AutoCAD-Customization/files/GUID-A6C680F2-DE2E-418A-A182-E4884073338A.htm).

El repositorio de desarrollo puede ser privado. El canal público contiene únicamente recursos autorizados y binarios de release; no recibe fuentes Python/.NET ni secretos. Protege `main`, limita el acceso de escritura y conserva la revisión de los LISPs y scripts, ya que son código ejecutable.

Los registros locales están en `%LOCALAPPDATA%\SINCAL\logs\sincal.log` y los incidentes estructurados en `%LOCALAPPDATA%\SINCAL\diagnostics\incidents.jsonl`. Ninguno se transmite automáticamente. Si los comandos CAD no aparecen, actualiza recursos, ejecuta Diagnóstico, vuelve a preparar la integración y reinicia CAD. Si una descarga falla, revisa conexión, proxy y antivirus antes de reintentar.
