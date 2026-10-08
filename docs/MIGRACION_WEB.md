# Migración de SINCAL Suite a interfaz de escritorio

Estado al 1 de octubre de 2026. SINCAL Suite continúa siendo una aplicación de
Windows. HTML, CSS y JavaScript se ejecutan dentro de su ventana WebView2 y usan
el núcleo Python local. La propuesta inicial de portal compartido quedó
descartada; no se requiere servidor público, dominio ni cuenta en nube.

La implementación está disponible en el repositorio, sin compilar ni sustituir
la aplicación instalada. La autorización pendiente es para compilar una versión
de prueba, no para publicar datos o instalar una release automáticamente.

## Inventario de funciones

- Home conserva presentación, créditos y sincronizador. Se puede comprobar el
  manifiesto, revisar los archivos y aplicar recursos verificados. La preparación
  de integración registra las rutas CAD del usuario tras confirmación.
- Documentación busca por título, etiquetas y contenido. El índice agrupa enlaces
  por categoría y no tiene un scroll interno. Las instrucciones específicas de
  la nueva UI se superponen al manual base sin cambiar el manual de Tk.
- Comandos en vivo ofrece BV, DL2, P0, PURGEALL, SETUP-A1, STO/ST0, W08, ZE,
  PLOTYA, VPTOGGLE y LAYORIGIN. Enter ejecuta. Los comandos personalizados admiten
  solo un nombre y requieren declaración de que son autónomos.
- El alcance de comandos puede ser dibujo activo o todos los documentos abiertos
  de una única instancia. Se confirma la lista y se recorre secuencialmente.
  Si cambia la lista antes de comenzar o falla una orden, no se continúa a ciegas.
- Conversión permite seleccionar varios DXF, motor AutoCAD/ZWCAD y carpeta de
  salida. Conserva los originales y rechaza destinos existentes/repetidos.
  Solo inicia una instancia temporal cuando el CAD del usuario está cerrado.
- Renombrado ofrece búsqueda/reemplazo, plan previo, detección de colisiones y
  revalidación de los archivos. No recorre subcarpetas ni cambia extensiones.
  Un fallo intenta revertir lo ya renombrado, sin sobrescribir otro archivo.
- Ubicación lee KML/KMZ, lista puntos geográficos, ofrece mapas calibrados,
  microajustes y croquis PNG. El mapa se descarga y verifica únicamente si falta.
  Las coordenadas PTL del proyecto no se usan como coordenadas geográficas.
- Consulta importa JSON sin modificarlo y muestra información ordenada de lo
  general a lo particular. Conserva OT, revisión y nombre, exporta TXT y comparte
  el mismo proyecto con Armaduras, Perfiles geofísicos y Estratigrafía.
- Armaduras mantiene entrada y salida independientes. Importa las dimensiones
  compatibles de zapata y esviaje del JSON; deja vacías las que no existen.
  Permite editar marca base, diámetro, separación, gancho, origen y estado activo.
- El cálculo usa el modelo existente: cantidades, longitudes, área, peso,
  ubicación, vistas y rol. La tabla se puede ampliar. Cada marca abre el fierro
  con geometría SVG, parciales desarrolladas, radio y longitud por eje.
- La zapata incorpora detección de moldajes, selección de contornos y envío de
  vistas FR, AA, BB, CC y EE, más despiece general. Verifica unidades y Model.
  D–D corresponde a muros; no se inventa un generador para elementos sin definir.
- Travesaños conserva los cinco cuadrantes y sus despieces. Las dos plantillas
  LISP se extrajeron intactas de Tk a un módulo compartido. El despiece exige
  haber generado ese cuadrante con esos parámetros en el dibujo.
- Perfiles geofísicos (antes Prospecciones) reutiliza lectura PDF/TXT y OCR local. Muestra tablas, valores
  oficiales, avisos, evidencia y confianza por celda; dibuja la vista del perfil.
  La inserción CAD requiere cotejar el OCR y no acepta perfiles con errores.
- Estratigrafía lee las tablas resumen VISAN de perforación y SPT de PDF con texto
  o TXT (validado con los cuatro sondajes de IMS Calera de Tango). No admite aún
  escaneos ni otros esquemas de tablas. Conserva las cifras publicadas: recuperación
  porcentual en azul, NSPT independiente y rechazo como R, sin convertirlo a 50.
  Los intervalos provienen del registro del operador, no de límites estimados de
  la figura general. Cada intervalo permite confirmar su hatch antes de insertar.
  La vista previa y el dibujo comparten las profundidades; se pueden incluir las
  tablas completas. La evidencia conserva páginas originales y avisos de diferencias
  entre resumen y partes diarios, sin corregirlas. El reconocimiento se puede
  guardar y abrir en JSON. La inserción exige cotejo, dibujo activo en metros y
  Model; crea un grupo editable, sin guardar el DWG. Copia los patrones del bloque
  PROSPECCIONES del maestro instalado y crea textos RomanD anotativos de 2,5 mm
  de altura de papel, según la escala anotativa activa. Se probó en AutoCAD 2025;
  la ejecución nativa en ZWCAD queda pendiente de verificación.
- Sesiones guarda instantáneas independientes, busca por estructura/OT/revisión,
  muestra tarjetas paginadas y permite cargar, importar y exportar. La importación
  antigua conserva el documento original dentro de la instantánea, pero no activa
  referencias CAD antiguas. Guarda recuperación de cambios cada 60 segundos.
- Diagnóstico crea resumen y ZIP sin adjuntar DWG, permite descargar registros
  y conserva la selección del motor usado por los scripts por carpeta.

## Interfaz y ejecución

Se incorporaron las 15 familias de paletas compartidas con Cadence más SINCAL,
modos oscuro/claro/sistema, fuentes locales regulares, tamaños de controles
heredados y zoom de texto 90/100/115 %. Los acentos se ajustan para mejorar su
contraste sobre el fondo seleccionado.

El menú izquierdo y el índice derecho se ocultan por separado. El panel central
conserva márgenes y un scroll de página; las tablas admiten desplazamiento
horizontal. Los botones tienen bordes rectos y sombra. El elemento seleccionado
usa texto resaltado y línea lateral. El indicador de trabajo utiliza la geometría
vectorial del puente, un mensaje y progreso real o indeterminado.

Las preferencias y sesiones se almacenan dentro del perfil Windows. Compartir
la misma cuenta del sistema comparte esos datos; no se ofrece aislamiento
mediante login propio ni respaldo remoto en esta entrega.

## Seguridad y registros

La API solo escucha en 127.0.0.1 y valida Host, Origin y token temporal. No hay
endpoint de shell ni de LISP libre. Los archivos se eligen en un diálogo nativo
y se referencian con identificadores opacos, no con rutas aportadas por HTTP.

COM se ejecuta en procesos aislados. La comprobación no abre CAD y vence a los
15 segundos. Los envíos verifican instancia, documento, disponibilidad y, cuando
corresponde, unidades, espacio y contorno. No hay reenvío automático si SendCommand
falla después de poder haber aceptado la orden.

Cancelar detiene la espera y el trabajador, no mata AutoCAD/ZWCAD ni deshace
cambios. CAD puede quedar esperando un punto o continuar procesando; se indica al
usuario. La finalización del trabajador no certifica la geometría ni que un
comando nativo haya tenido el efecto esperado. Algunos comandos guardan o
exportan por sí mismos.

Cada operación genera un registro local redactado. Se conservan como máximo
100 registros durante 30 días, limitando el detalle en curso a 2 MB por archivo.
Los temporales internos propios vencen a los 7 días. Las sesiones formales,
los DWG y los archivos ajenos a esas carpetas no se limpian.

## Pruebas realizadas

- Suite Python sin la prueba compiladora de registros: 180 pruebas aprobadas,
  2 omitidas y 21 subpruebas aprobadas.
- Comprobación sintáctica de app.js, tools.js y rebar.js.
- Comparación textual de las dos plantillas de travesaño: idénticas a las
  originales, cambiando únicamente su ubicación y el envoltorio Python.
- Pruebas de persistencia, importación de sesiones, recuperación, permisos de
  archivo, renombrado, retención, contraste, geometría y errores de ejecución.
- Pruebas simuladas de cambio de dibujo, envío incierto y detención del recorrido
  por varios dibujos. No ejecutan órdenes sobre planos reales.
- Inspección de la ventana nativa WebView2 y prueba de navegación en el frontend.
- Carga de un proyecto ficticio, cálculo de seis marcas, detalle individual y
  guardado. El detalle de prueba mostró gancho de 100 cm y radio de 6,6 cm para Ø22.
- Cambios de tema/paleta y zoom, revisión de módulos sin errores JavaScript.
- Comprobación real de solo lectura: AutoCAD 2025 respondió disponible con un
  documento abierto. No se enviaron comandos ni se alteró ese plano.

La prueba test_script_logs.py quedó fuera porque compila un ejecutable auxiliar.
No se ha compilado aplicación, plugin, instalador ni ese auxiliar en esta fase.

## Verificaciones pendientes antes de publicar

Se debe compilar con autorización y probar el ejecutable, el selector nativo de
archivos y WebView2 en un equipo de instalación. La configuración alternativa
está preparada, pero un spec escrito no equivale a un binario validado.

Falta la aceptación integral sobre dibujos desechables en AutoCAD 2025/2027 y
ZWCAD: vistas, despieces, perfiles, comandos y conversión. La lectura COM real y
los dobles de prueba no sustituyen esa revisión geométrica. También debe
ensayarse el OCR completo con su runtime empaquetado.

Los scripts masivos CMD conservan su funcionamiento y sus registros anteriores.
No se ha reescrito ni certificado cada script de ploteo durante esta migración.
Las armaduras de muros, alas y otros componentes que estaban en espera continúan
sin definición nueva; no se consideran implementadas por tener un apartado UI.

## Preparación de compilación

desktop_main.py es la entrada alternativa y atiende los trabajadores CAD del
ejecutable sin consola. SINCAL_Web.spec incluye interfaz y recursos visuales;
tools/build_release.ps1 acepta DesktopWeb para seleccionarlo. El modo de
compilación habitual sigue usando el cliente Tk anterior.

Antes de ejecutar el pipeline hay que autorizar la compilación, instalar las
dependencias de escritorio y asignar una versión nueva para no sobrescribir
artefactos de una release previa. No se han cambiado versión, publicación,
instalación, sitio corporativo ni repositorio Cadence.
