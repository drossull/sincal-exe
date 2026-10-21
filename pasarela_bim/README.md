# Pasarela BIM — generador topológico

Editor local para construir una pasarela desde un lienzo vacío a partir de sus
conexiones y generar sólidos identificados en FreeCAD. Incluye un caso conceptual de Los
Batros, reconstruido de las láminas G101-PT-PD-PLA-3001 a 3021, revisión B.

## Abrir la herramienta

Desde la raíz del repositorio, ejecutar `iniciar_pasarela.bat`, o:

```powershell
python -m pasarela_bim
```

El editor abre en `http://127.0.0.1:8766`. Necesita Python 3.10 o posterior y
FreeCAD 1.1 (Qt 6) para generar; el editor y la validación usan sólo la biblioteca estándar.
No se instala nada ni se modifica el arranque de SINCAL. Para cambiar puerto:
`python -m pasarela_bim --port 8767`. La opción `--sin-navegador` permite iniciar
el servidor sin abrir una ventana de navegador.

FreeCAD se detecta en PATH o en `Program Files/FreeCAD*/bin`. Si está en otra
ubicación, definir `PASARELA_FREECAD` con la ruta a su ejecutable GUI. La
generación usa un proceso separado y oculto con Qt offscreen, con perfiles de
configuración propios y sin documentos previos. Cada ejecución tiene una
carpeta nueva en `%LOCALAPPDATA%\SINCAL\pasarela-bim\generados`.
`--data-dir` o `PASARELA_DATA_DIR` permiten cambiar la carpeta de datos.

También está preparado como módulo opcional de SINCAL, independiente del
ejecutable general. Se instala desmarcado por defecto en el instalador principal
o posteriormente desde **Pasarela BIM → Instalar paquete**. El paquete sólo
incluye este editor y su motor de generación; FreeCAD permanece externo.
Los proyectos y resultados quedan fuera de la carpeta del módulo para conservarlos
al actualizar o desinstalar el complemento. Para actualizar, guarda el JSON y
usa **Cerrar módulo** desde SINCAL.

## Qué significa topología aquí

El recorrido es un grafo: los nudos son encuentros y las conexiones tienen una
función (cruce, rampa, descanso, retorno o escalera), independiente de su sección.
Un encuentro puede existir sin columna. Las posiciones y cotas se asignan a los nudos; una pieza obtiene su
dirección y extremos de esas relaciones, sin depender del orden de las listas.

La infraestructura es otra relación: un dado puede sostener varias columnas.
Compartir dado no crea una conexión peatonal. La validación comprueba ambos
tipos de relación por separado. Se admiten redes conectadas con bifurcaciones o
circuitos; sólo un camino simple tiene un recorrido lineal único.

Los identificadores del proyecto y sus elementos deben mantenerse al regenerar.
El adaptador deriva identificadores persistentes de ellos. El JSON es la fuente
paramétrica; editarlo y volver a generar produce una nueva instantánea. Esta
versión no sincroniza de vuelta cambios manuales hechos sobre sólidos FreeCAD.

## Flujo de uso

1. **Nuevo proyecto**: nombre, Este/Norte/cota del origen, orientación y gálibo.
   El origen local `(0,0,0)` es el punto medio del atravieso al nivel del terreno.
   X sigue el atravieso, Y es transversal local y Z positivo apunta arriba.
2. Cargar una **planta DWG/DXF** como referencia, si está disponible. Puede
   cancelarse el diálogo inicial del atravieso y reabrirlo después de cargarla.
3. **Instalar atravieso**: previsualizar longitud, ancho, canto y uno o dos vanos.
   Su cota inicial es `cota de carretera local + gálibo + canto`.
4. Usar **+** en un nodo para añadir una conexión X+, X−, Y+ o Y−. Los encuentros
   pueden ramificarse; las fundaciones compartidas son otra relación independiente.
5. Seleccionar tramos para editar su sección gráfica: cajón, losa maciza o
   escalera recta. Una familia puede aplicarse a varios tramos o duplicarse.
6. Completar apoyos y fundaciones, individuales o compartidas. Los cambios de
   cota muestran sus efectos antes de aplicarse y respetan las cotas fijas.
7. **Guardar JSON** en cualquier momento, también con datos pendientes. **Abrir
   JSON** conserva familias, conexiones, identidad, georreferencia y fondo CAD.
8. Completar los pendientes, validar y **Generar en FreeCAD**. Cada ejecución
   produce un nuevo modelo y vistas en una carpeta independiente.

## Ejes de estructura y elevaciones

El atravieso tiene un eje longitudinal y cada recorrido peatonal tiene otro.
Los ejes contienen una cadena ordenada de identificadores de tramos; no duplican
sus coordenadas. Un recorrido puede incluir rampas, descansos, giros y escaleras.
Una bifurcación necesita otra cadena. Cada cepa y cada estribo tienen además su
propio eje de apoyo, identificado en todas las elevaciones que pasan por ese nodo.

Al instalar el atravieso y añadir conexiones se crean o prolongan sus ejes.
**+ Eje** permite definir una cadena manualmente. **Proponer ejes** incorpora
ejes a un archivo anterior sólo después de revisar y aplicar su propuesta.
La identidad UUID se conserva al cambiar un rótulo o prolongar una cadena.
Eliminar un eje conserva sus piezas y deja pendiente su nueva asociación.

**Mover eje** previsualiza una traslación X/Y en metros de todos sus nodos,
piezas y apoyos. Las fundaciones siguen a sus nodos asociados; una fundación
compartida se comprueba y avisa si sólo se mueve parte de sus apoyos. La opción
**Trasladar también el conjunto conectado** mueve rígidamente el componente
topológico completo. Se bloquean posiciones fijas, quiebres del atravieso,
longitudes incompatibles con retranqueos y cambios de la pendiente fija del 8 %.
Se conserva la posición geográfica de los elementos fuera del alcance. Si cambia
el punto medio del atravieso principal, se actualizan Este/Norte del origen y se
reexpresan las coordenadas locales para mantener allí el `(0,0,0)` en planta.
La vista previa indica este cambio de marco antes de aplicarlo.

**Elevación por eje** muestra estaciones acumuladas en planta, distancias entre
nodos, cotas locales y ejes de apoyos. Los recorridos con giros se presentan como
elevaciones desarrolladas. El editor muestra la envolvente longitudinal; los
apoyos son referencias de eje y niveles. La generación guarda referencias de
ejes en FreeCAD, sin contarlas como hormigón, y exporta una elevación SVG por eje
longitudinal, además de las cuatro vistas base. Las elevaciones exportadas
incluyen rasantes, cantos, retranqueos y referencias de los apoyos: todavía no
son planos constructivos completos de cepas y fundaciones. Todas estas
asociaciones viajan en el JSON intercambiable en metros.

La interfaz y el JSON de intercambio utilizan **metros**. El adaptador interno
convierte a milímetros para FreeCAD. `ancho_m` es el ancho estructural superior
de la viga; no representa automáticamente el ancho libre entre barandas.

## Coordenadas, norte y planta

`proyecto.georreferencia` contiene `este_m`, `norte_m`, `cota_m`,
`norte_desde_x_horario_deg` y un texto opcional `crs`. El ángulo se mide desde X
positivo en sentido horario en planta: 0° sitúa el norte hacia X+, y 270° hacia
Y+. La flecha del lienzo y la transformación del fondo utilizan la misma regla.
Para un ángulo θ y coordenadas locales x/y/z en metros:

```
Este  = Este_origen − x·sin(θ) − y·cos(θ)
Norte = Norte_origen + x·cos(θ) − y·sin(θ)
Cota  = Cota_origen + z
```

No se efectúa una reproyección entre sistemas cartográficos. El DWG/DXF debe
estar en el mismo sistema Este/Norte declarado. La planta es una referencia 2D;
sus entidades y capas quedan embebidas en el JSON en metros. No se convierte
automáticamente en una superficie de terreno ni se extrae una rasante viaria.
La comprobación inicial de gálibo usa la cota viaria local introducida y el
intradós de los tramos de cruce, sin certificar normativa.

El lector admite líneas, polilíneas con arcos, círculos, arcos, puntos, textos y
bloques básicos. Indica qué entidades no representa. Las referencias externas
deben estar vinculadas; los objetos específicos de Civil 3D pueden necesitar
exportación a entidades básicas. La carga DWG utiliza AutoCAD Core Console
instalado y una copia privada, sin utilizar la sesión CAD abierta. DXF ASCII se
lee sin AutoCAD. Máximo 20 MB de entrada, 25 000 entidades y 250 000 puntos.

## Contrato de intercambio, versión 2

Los archivos nuevos usan `version: 2`, `proyecto.unidades: "m"` y campos
dimensionales con sufijo `_m`. Se conserva la lectura del formato histórico
v1/mm. Las magnitudes dentro de proyecto/georreferencia/emplazamiento permanecen
en metros incluso en el adaptador interno; los identificadores de familia no
se convierten. Los UUID internos son independientes de las etiquetas editables.

| Colección | Función |
| --- | --- |
| `proyecto` | Identidad, estado, unidades y referencia del caso. |
| `nodos` | Identidad, tipo, X/Y y Z de superficie de paso. |
| `tramos` | Nudos de origen y destino, familia, ancho, retranqueos y rasante. |
| `familias` | Secciones cajón o macizas y perfil de canto. |
| `soportes` | Columna o estribo en los nudos que requieren apoyo físico, vinculado a su fundación. |
| `fundaciones` | Nudos sustentados, dimensiones, cota, orientación y pilotes. |
| `pendientes_documentales` | Dudas de origen conservadas como avisos. |
| `simplificaciones` | Límites de representación del caso. |
| `emplazamiento` | Planta de referencia y capas embebidas, sin rutas necesarias en otro equipo. |

La validación de borradores diferencia `errores` de `pendientes`. Un borrador
sin errores puede guardarse aunque `generable` sea falso. La generación exige
completar todos los datos necesarios. Los ejemplos históricos mantienen sus
aproximaciones documentadas y requieren clasificación de sus tramos para
aplicar las reglas nuevas.

El centro de un dado es el centroide XY de sus nudos. Su eje longitudinal se
orienta desde el primer nudo al último, salvo `angulo_deg` explícito. Los pilotes
se posicionan con `dx_m`/`dy_m` en ese marco local. Las alturas de columnas se
obtienen entre la cara superior del dado y su `cota_superior_m`.

La rasante de un tramo es una secuencia `{t, f}`: `t` es la fracción de distancia
en planta entre nudos, y `f` el progreso de elevación entre sus cotas. Se exige
inicio `(0,0)`, fin `(1,1)`, `t` creciente y `f` no decreciente. Un intervalo con
`f` constante forma un descanso. En los proyectos nuevos, las rampas tienen
**8 % fijo** en sus partes inclinadas,
como regla solicitada para esta herramienta. Descansos y retornos son
horizontales; las escaleras usan huella y contrahuella. La pendiente no es un
parámetro editable. Al modificar una cota, el editor previsualiza el nuevo
desarrollo y los nodos que acompaña. Los conflictos con posiciones fijas o
circuitos se señalan antes de aplicar. Los retranqueos
recortan esa rasante y permiten distinguir longitud entre ejes y longitud de pieza.

El perfil de canto opcional usa `{t, canto_m}`. Así los cambios de rasante y
canto permanecen separados. El motor construye secciones en las estaciones de
ambos perfiles, vacía el cajón y conserva macizados en extremos.

En encuentros incidentes, los retornos y capiteles se recortan contra las vigas.
Entre vigas se conserva primero la de mayor canto, después la de mayor longitud
y finalmente se desempata por identificador. Es una regla geométrica de este
prototipo, no un detalle constructivo. El informe registra los recortes y los
solapes volumétricos restantes; una validación de sólidos no implica ausencia
de solapes. Las longitudes nominales permanecen como datos de entrada.

## Alcance de Los Batros

El caso contiene 16 nudos, 13 vigas, 2 retornos, 14 fustes, 2 estribos, 10 dados
y 18 pilotes. Incluye cuatro familias de vigas y una de retorno macizo.
Las coordenadas son locales y no sirven para replanteo. Longitudes y cantos
nominales proceden de la referencia; rasantes, retranqueos y algunas secciones
son aproximaciones explícitas para probar el motor.

Los capiteles, estribos y cierres son envolventes simplificadas. No se incluyen
armaduras, geometría de pretensado, aparatos de apoyo, barandas, bombeo ni la
resolución de los once pendientes documentales. Las cantidades describen sólo
los sólidos generados. No hay comprobación resistente ni normativa.

Las vistas generadas son una base para planos. Esta versión no produce el juego
ejecutivo de 21 láminas, cotas constructivas, detalles de armadura ni IFC. El
modelo conserva geometría, identidad, material y relaciones para desarrollar
esas salidas a continuación.

## Validación y ejecución sin editor

```powershell
python -m pasarela_bim --validar pasarela_bim/ejemplos/los_batros.json
python -m pasarela_bim --generar pasarela_bim/ejemplos/los_batros.json
python -m unittest discover -s tests/pasarela_bim -v
```

La generación rechaza entradas incoherentes, comprueba sólidos y volúmenes,
guarda el FCStd y lo vuelve a abrir. El informe conserva los resultados de esa
verificación. No se sobrescriben carpetas de ejecuciones previas.

La prueba `test_freecad_integration.py` se omite fuera del Python de FreeCAD.
Ejecutada con ese intérprete, genera dos modelos y verifica que mover C8 cambie
la geometría conectada sin alterar identidades ni duplicar fundaciones.
