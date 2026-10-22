"""Materialización conceptual del grafo de pasarela en FreeCAD.

Se ejecuta con el Python de FreeCAD. La configuración es la fuente paramétrica;
los sólidos se regeneran, no son objetos con un árbol de operaciones editable.
Las vistas TechDraw sí conservan sus vínculos con los sólidos del documento.
"""

from __future__ import annotations

from .seccion import familia_del_tramo

import json
import hashlib
import math
import re
import time
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from xml.sax.saxutils import escape


_ESPACIO_IDS = uuid.UUID("28bf1a8e-d1c2-50d1-bc25-63bfd07efe62")


def _nombre(valor):
    return re.sub(r"[^A-Za-z0-9_]", "_", str(valor))


def _interpolar(puntos, t, clave_x="t", clave_y="f"):
    puntos = sorted(puntos, key=lambda p: p[clave_x])
    if t <= puntos[0][clave_x]:
        return float(puntos[0][clave_y])
    for a, b in zip(puntos, puntos[1:]):
        if t <= b[clave_x]:
            d = b[clave_x] - a[clave_x]
            return float(a[clave_y] + (b[clave_y] - a[clave_y]) * (t-a[clave_x])/d)
    return float(puntos[-1][clave_y])


def _perfil_canto(familia):
    return familia.get("perfil_canto") or [
        {"t": 0.0, "canto_mm": familia["canto_mm"]},
        {"t": 1.0, "canto_mm": familia.get("canto_fin_mm", familia["canto_mm"])},
    ]


def _canto(familia, t):
    return _interpolar(_perfil_canto(familia), t, clave_y="canto_mm")


def _z(tramo, nodos, t):
    a, b = nodos[tramo["desde"]], nodos[tramo["hasta"]]
    return float(a["z"] + (b["z"]-a["z"]) * _interpolar(tramo["rasante"], t))


def _estaciones(tramo, familia, inicio, fin):
    largo = tramo["longitud_planta_mm"]
    ts = {float(inicio/largo), float(fin/largo)}
    for p in list(tramo["rasante"]) + list(_perfil_canto(familia)):
        if inicio/largo < p["t"] < fin/largo:
            ts.add(float(p["t"]))
    return sorted(ts)


def _wire(Part, App, centro, ux, uy, perfil):
    puntos = [App.Vector(centro[0]-uy*x, centro[1]+ux*x, centro[2]+z)
              for x, z in perfil]
    return Part.makePolygon(puntos + [puntos[0]])


def _loft(Part, wires, etiqueta):
    shape = Part.makeLoft(wires, True, True)
    if shape.isNull() or not shape.isValid() or not shape.Solids or shape.Volume <= 1e-5:
        raise ValueError(f"{etiqueta}: loft sin sólido válido y volumen positivo")
    return shape


def _tramo_shape(Part, App, tramo, familia, nodos):
    familia = familia_del_tramo(familia, tramo, nodos)
    if familia.get("tipo") == "escalera":
        return _escalera_shape(Part, App, tramo, familia)
    largo = tramo["longitud_planta_mm"]
    inicio = float(tramo.get("retranqueo_inicio_mm", 0))
    fin = largo-float(tramo.get("retranqueo_fin_mm", 0))
    ancho = float(tramo["ancho_mm"])
    tipo_familia = familia.get("tipo", "maciza" if tramo["tipo"] == "retorno" else "cajon")
    maciza = tipo_familia == "maciza"
    sup = ancho if maciza else float(familia.get("ancho_alma_superior_mm", ancho))
    inf = float(familia.get("ancho_inferior_mm", ancho))
    esp_sup = float(familia.get("losa_superior_mm", familia["canto_mm"]/4))
    esp_inf = float(familia.get("losa_inferior_mm", familia["canto_mm"]/4))
    alma = float(familia.get("alma_mm", 0))
    if ancho < sup or min(sup, inf, esp_sup, esp_inf) <= 0:
        raise ValueError(f"{tramo['id']}: dimensiones de sección incompatibles")
    pendiente = familia.get("pendiente_transversal_pct", 1)
    if isinstance(pendiente, bool) or not isinstance(pendiente, (int, float)) or not math.isfinite(pendiente) or pendiente != 1:
        raise ValueError("La pendiente transversal debe ser 1 % a dos aguas")
    descenso = pendiente*ancho/200
    nodo = nodos[tramo["desde"]]

    def secciones(s0, s1, interior=False):
        salida = []
        for t in _estaciones(tramo, familia, s0, s1):
            h = _canto(familia, t)
            if not maciza and h <= esp_sup+esp_inf:
                raise ValueError(f"{tramo['id']}: canto insuficiente para las losas")
            if descenso >= (h if maciza else esp_sup):
                raise ValueError("La pendiente transversal agota el espesor en los bordes")
            if interior:
                # Espesor de alma horizontal en esta aproximación conceptual.
                bt = sup-2*alma
                bb = inf+(sup-inf)*esp_inf/(h-esp_sup)-2*alma
                if min(bt, bb) <= 0:
                    raise ValueError(f"{tramo['id']}: hueco incompatible con espesor de alma")
                perfil = [(-bt/2, -esp_sup), (bt/2, -esp_sup),
                          (bb/2, -h+esp_inf), (-bb/2, -h+esp_inf)]
            elif maciza:
                perfil = [(-ancho/2, 0), (ancho/2, 0), (inf/2, -h), (-inf/2, -h)]
            else:
                perfil = [(-ancho/2, 0), (ancho/2, 0),
                          (ancho/2, -esp_sup), (sup/2, -esp_sup),
                          (inf/2, -h), (-inf/2, -h),
                          (-sup/2, -esp_sup), (-ancho/2, -esp_sup)]
                # Evitar aristas nulas cuando no hay ala lateral.
                perfil = [p for i, p in enumerate(perfil) if p != perfil[i-1]]
            if not interior and descenso > 0:
                perfil[:2] = [(-ancho/2, -descenso), (0, 0), (ancho/2, -descenso)]
            centro = (nodo["x"]+tramo["ux"]*largo*t,
                      nodo["y"]+tramo["uy"]*largo*t, _z(tramo, nodos, t))
            salida.append(_wire(Part, App, centro, tramo["ux"], tramo["uy"], perfil))
        return salida

    shape = _loft(Part, secciones(inicio, fin), tramo["id"])
    if tipo_familia == "cajon":
        macizado = float(familia.get("macizado_mm", 500))
        if macizado != 500:
            raise ValueError("El macizado debe ser 0,50 m en cada extremo")
        if fin-inicio > 2*macizado+1e-4:
            hueco = _loft(Part, secciones(inicio+macizado, fin-macizado, True),
                         tramo["id"]+"_hueco")
            shape = shape.cut(hueco).removeSplitter()
    return shape


def _escalera_shape(Part, App, tramo, familia):
    """Losa inclinada con peldaños horizontales, extruida transversalmente.

    Los puntos de llegada son cotas de paso. El canto es vertical bajo la
    rasante de referencia; huella y contrahuella se deducen, no se dimensionan.
    """
    inicio, fin = tramo["inicio"], tramo["fin"]
    if inicio[2] > fin[2]:
        inicio, fin = fin, inicio
    largo = math.hypot(fin[0]-inicio[0],fin[1]-inicio[1])
    ux, uy = (fin[0]-inicio[0])/largo,(fin[1]-inicio[1])/largo
    alto = fin[2]-inicio[2]
    numero = familia["numero_peldanos"]
    huella, contrahuella = largo/numero,alto/numero
    canto, ancho = familia["canto_mm"],tramo["ancho_mm"]
    perfil = [(0,0)]
    for i in range(numero):
        perfil.extend([(i*huella,(i+1)*contrahuella),((i+1)*huella,(i+1)*contrahuella)])
    perfil.extend([(largo,alto-canto),(0,-canto)])
    puntos = [App.Vector(inicio[0]+ux*s+uy*ancho/2,
                         inicio[1]+uy*s-ux*ancho/2,inicio[2]+z) for s,z in perfil]
    wire = Part.makePolygon(puntos+[puntos[0]])
    shape = Part.Face(wire).extrude(App.Vector(-uy*ancho,ux*ancho,0)).removeSplitter()
    if not shape.isValid() or not shape.Solids or shape.Volume <= 0:
        raise ValueError(f"{tramo['id']}: escalera sin sólido válido")
    return shape


def _bloque(Part, App, largo, ancho, alto, x, y, z, angulo=0):
    shape = Part.makeBox(largo, ancho, alto, App.Vector(-largo/2, -ancho/2, 0))
    shape.rotate(App.Vector(), App.Vector(0, 0, 1), angulo)
    shape.translate(App.Vector(x, y, z))
    return shape


def _capitel_shape(Part, App, soporte, nodo, conectados, familias, nodos):
    """Cuñas simplificadas que alcanzan el intradós de cada extremo conectado."""
    partes = []
    base = float(soporte["cota_superior_mm"])
    diametro = float(soporte.get("diametro_mm", 1000))
    for tramo in conectados:
        familia = familia_del_tramo(familias[tramo["familia"]], tramo, nodos)
        en_inicio = tramo["desde"] == nodo["id"]
        signo = 1 if en_inicio else -1
        largo = tramo["longitud_planta_mm"]
        retiro = float(tramo.get("retranqueo_inicio_mm" if en_inicio else
                                 "retranqueo_fin_mm", 0))
        extension = max(diametro/2+150, retiro+400)
        ancho = max(diametro+200, min(tramo["ancho_mm"], 1400))
        wires = []
        for s in (-diametro/2, extension):
            distancia = max(0, min(largo, s if en_inicio else largo-s))
            t = distancia/largo
            techo = _z(tramo, nodos, t)-_canto(familia, t)
            if techo < base-0.1:
                raise ValueError(f"{nodo['id']}: el soporte invade el intradós de {tramo['id']}")
            if techo <= base+0.1:
                return None
            centro = (nodo["x"]+signo*tramo["ux"]*s,
                      nodo["y"]+signo*tramo["uy"]*s, base)
            perfil = [(-ancho/2, 0), (ancho/2, 0),
                      (ancho/2, techo-base), (-ancho/2, techo-base)]
            wires.append(_wire(Part, App, centro, signo*tramo["ux"],
                               signo*tramo["uy"], perfil))
        partes.append(_loft(Part, wires, "Capitel_"+nodo["id"]))
    if not partes:
        return None
    shape = partes[0]
    for parte in partes[1:]:
        shape = shape.fuse(parte)
    return shape.removeSplitter()


def _prop(obj, tipo, nombre, valor, grupo="Pasarela BIM"):
    if nombre not in obj.PropertiesList:
        obj.addProperty(tipo, nombre, grupo)
    setattr(obj, nombre, valor)


def _identidad(obj, proyecto, rol, identificador, datos, nodos=(), parametros_portables=None,
               material="Hormigón (calidad por definir)"):
    _prop(obj, "App::PropertyString", "IDTopologico", str(identificador))
    _prop(obj, "App::PropertyString", "UUIDBIM", str(uuid.uuid5(
        _ESPACIO_IDS, f"{proyecto.get('uuid',proyecto['id'])}:{rol}:{datos.get('uuid',identificador)}")))
    if datos.get("uuid"):
        _prop(obj, "App::PropertyString", "UUIDOrigen", str(datos["uuid"]))
    _prop(obj, "App::PropertyString", "RolBIM", rol)
    _prop(obj, "App::PropertyString", "EstadoModelo", "conceptual")
    if material is not None:
        _prop(obj, "App::PropertyString", "MaterialBIM", material)
    _prop(obj, "App::PropertyString", "FuenteParametros",
          str(datos.get("fuente", proyecto.get("fuente", "Parámetros del proyecto"))))
    _prop(obj, "App::PropertyString", "ParametrosJSON", json.dumps(
        datos if parametros_portables is None else parametros_portables, ensure_ascii=False))
    _prop(obj, "App::PropertyString", "UnidadesParametros", "m")
    _prop(obj, "App::PropertyStringList", "NodosTopologicos", list(nodos))


def _validar_shape(obj):
    s = obj.Shape
    if s.isNull() or not s.isValid() or not s.Solids or s.Volume <= 1e-5:
        raise ValueError(f"{obj.Name}: geometría inválida o sin volumen positivo")
    return float(s.Volume)


def _recortar_encuentro(obj, cortantes):
    inicial = obj.Shape.Volume
    shape = obj.Shape
    pares = []
    for cortante in cortantes:
        anterior = shape.Volume
        shape = shape.cut(cortante.Shape)
        eliminado = max(0.0, anterior-shape.Volume)
        if eliminado > 1000:
            pares.append({"cortante":cortante.Name,
                          "volumen_recortado_m3":round(eliminado/1e9,8)})
    shape = shape.removeSplitter()
    obj.Shape = shape
    _validar_shape(obj)
    recortado = max(0.0, inicial-shape.Volume)
    _prop(obj,"App::PropertyString","RecorteEncuentroJSON",json.dumps({
        "elementos":[c.Name for c in cortantes],"volumen_recortado_mm3":recortado,
        "pares":pares}))
    return recortado


def _solapes(objetos):
    salida = []
    for i, a in enumerate(objetos):
        ba = a.Shape.BoundBox
        for b in objetos[i+1:]:
            bb = b.Shape.BoundBox
            if any(min(getattr(ba,e+"Max"),getattr(bb,e+"Max"))-
                   max(getattr(ba,e+"Min"),getattr(bb,e+"Min")) <= 0.01 for e in "XYZ"):
                continue
            volumen = a.Shape.common(b.Shape).Volume
            if volumen > 1000.0:  # 1 cm³: se excluye ruido numérico de caras en contacto.
                salida.append({"a":a.Name,"b":b.Name,"volumen_m3":round(volumen/1e9,8)})
    return salida


def _crear_vistas(doc, objetos, salida, titulo, avisos):
    import FreeCAD as App
    if not App.GuiUp:
        avisos.append("Vistas omitidas: se requiere FreeCAD GUI, no FreeCADCmd ni Python sin GUI.")
        return []
    # NormalColor no existe como propiedad por vista en FreeCAD 1.1. El perfil
    # del proceso se ajusta solo durante la exportación y se restaura siempre.
    colores = App.ParamGet("User parameter:BaseApp/Preferences/Mod/TechDraw/Colors")
    normal_anterior = colores.GetUnsigned("NormalColor", 0x000000FF)
    colores.SetUnsigned("NormalColor", 0x1F2938FF)
    try:
        return _crear_vistas_gui(doc, objetos, salida, titulo, avisos)
    finally:
        colores.SetUnsigned("NormalColor", normal_anterior)


def _crear_vistas_gui(doc, objetos, salida, titulo, avisos):
    import FreeCAD as App
    if not App.GuiUp:
        avisos.append("Vistas omitidas: se requiere FreeCAD GUI, no FreeCADCmd ni Python sin GUI.")
        return []
    import FreeCADGui as Gui
    import TechDrawGui

    plantilla = salida/"plantilla_A1.svg"
    plantilla.write_text('''<svg xmlns="http://www.w3.org/2000/svg" xmlns:freecad="http://www.freecadweb.org/wiki/index.php?title=Svg_Namespace" width="841mm" height="594mm" viewBox="0 0 841 594">
<rect x="10" y="10" width="821" height="574" fill="none" stroke="#64748b" stroke-width="0.35"/>
<path d="M10 550H831 M420 40V550 M10 350H831" fill="none" stroke="#cbd5e1" stroke-width="0.2"/>
<g font-family="Arial" fill="#0f172a"><text x="20" y="28" font-size="7">'''+escape(titulo)+'''</text>
<text x="20" y="45" font-size="4">PLANTA</text><text x="435" y="45" font-size="4">ISOMETRÍA</text>
<text x="20" y="366" font-size="4">ALZADO - DIRECCIÓN Y</text><text x="435" y="366" font-size="4">ALZADO - DIRECCIÓN X</text>
<text x="20" y="565" font-size="5">MODELO CONCEPTUAL - VISTAS ASOCIADAS AL MODELO</text>
<text x="20" y="576" font-size="3.5">Geometría simplificada. Sin dimensionamiento estructural, armaduras ni detalle constructivo. Unidades del modelo: mm.</text></g></svg>''', encoding="utf-8")
    page = doc.addObject("TechDraw::DrawPage", "LAMINA_A1")
    template = doc.addObject("TechDraw::DrawSVGTemplate", "PLANTILLA_A1")
    template.Template = str(plantilla)
    page.Template = template
    bb = App.BoundBox()
    for obj in objetos:
        bb.add(obj.Shape.BoundBox)
    # Dimensiones proyectadas conservadoras para no invadir el cuadro de otra vista.
    planta = min(340/max(bb.XLength, 1), 270/max(bb.YLength, 1))
    elev_y = min(340/max(bb.XLength, 1), 145/max(bb.ZLength, 1))
    elev_x = min(340/max(bb.YLength, 1), 145/max(bb.ZLength, 1))
    iso = min(330/max(bb.XLength+bb.YLength, 1),
              260/max((bb.XLength+bb.YLength)*0.58+bb.ZLength, 1))
    descripciones = [
        ("PLANTA", (0,0,1), (1,0,0), 210, 390, planta),
        ("ISOMETRIA", (1,-1,1), (1,1,0), 625, 390, iso),
        ("ALZADO_Y", (0,-1,0), (1,0,0), 210, 145, elev_y),
        ("ALZADO_X", (1,0,0), (0,1,0), 625, 145, elev_x),
    ]
    vistas = []
    for nombre, direccion, horizontal, x, y, escala in descripciones:
        view = doc.addObject("TechDraw::DrawViewPart", nombre)
        view.Source = objetos
        view.Direction = App.Vector(*direccion)
        view.XDirection = App.Vector(*horizontal)
        page.addView(view)
        view.ScaleType = "Custom"
        view.Scale = escala
        view.X, view.Y = x, y
        if "HardHidden" in view.PropertiesList:
            view.HardHidden = False
        if "SmoothVisible" in view.PropertiesList:
            view.SmoothVisible = False
        view.ViewObject.LineWidth = 0.25
        view.ViewObject.FaceColor = (1.0, 1.0, 1.0)
        view.Label = nombre.replace("_", " ")+f" (1:{1/escala:.1f})"
        vistas.append(view)
    doc.recompute()
    # La exportación GUI necesita que exista la escena de la página. Un FCStd
    # puede tener proyecciones correctas pero exportar un SVG vacío si no se
    # materializa su página en el visor, incluso con Qt fuera de pantalla.
    Gui.activeDocument().getObject(page.Name).show()
    # FreeCAD 1.1 calcula las aristas TechDraw en trabajadores. El test oficial
    # DrawViewPartTest usa QEventLoop para dejar completar esas proyecciones.
    from PySide6 import QtCore
    limite = time.monotonic()+45
    while True:
        loop = QtCore.QEventLoop()
        QtCore.QTimer.singleShot(200, loop.quit)
        loop.exec()
        if all(len(v.getVisibleEdges()) > 0 and "Up-to-date" in v.State for v in vistas):
            break
        if time.monotonic() >= limite:
            raise RuntimeError("TechDraw no terminó las cuatro proyecciones dentro de 45 segundos")
    # Dejar procesar la actualización de la escena antes de exportarla.
    loop = QtCore.QEventLoop()
    QtCore.QTimer.singleShot(250, loop.quit)
    loop.exec()
    archivos = []
    svg = salida/"vistas_A1.svg"
    try:
        TechDrawGui.exportPageAsSvg(page, str(svg))
        if svg.is_file() and svg.stat().st_size > 3000:
            archivos.append(str(svg))
        else:
            raise ValueError("La página exportada no contiene geometría visible")
    except Exception as exc:
        avisos.append(f"No se pudo exportar la página SVG: {exc}")
    # El PNG se obtiene del SVG de la página, evitando dependencia de OpenGL.
    if str(svg) in archivos:
        try:
            from PySide6 import QtCore, QtGui, QtSvg
            renderer = QtSvg.QSvgRenderer(str(svg))
            if not renderer.isValid():
                raise ValueError("SVG exportado no válido")
            png = salida/"vistas_A1.png"
            im = QtGui.QImage(2523, 1782, QtGui.QImage.Format_ARGB32)
            im.fill(QtGui.QColor("white"))
            painter = QtGui.QPainter(im)
            renderer.render(painter, QtCore.QRectF(0, 0, 2523, 1782))
            painter.end()
            if not im.save(str(png)):
                raise ValueError("No se pudo guardar la imagen de la lámina")
            archivos.append(str(png))
        except Exception as exc:
            avisos.append(f"No se pudo obtener PNG de las vistas: {exc}")
    return archivos


def _crear_ejes(doc, Part, App, datos, portable, anclas, por_id, revision):
    """Referencias sin material ni volumen; nunca entran en la lista de sólidos."""
    ejes = datos.get("ejes_resueltos", [])
    if not ejes:
        return []
    grupo = doc.addObject("App::DocumentObjectGroup", "EjesDeReferencia")
    grupo.Label = "Ejes de referencia · sin cantidades"
    referencias = {e["id"]: e for e in portable.get("ejes", [])}
    objetos = []
    for eje in ejes:
        apoyo = eje["tipo"] == "apoyo"
        if apoyo:
            # La extensión vertical sólo hace visible el marcador, no dimensiona
            # el apoyo. El nodo y las cotas declaradas siguen siendo la fuente.
            base = min([eje["z"]] + [f["cota_inferior_mm"] for f in eje["fundaciones"]])
            puntos = [[eje["x"], eje["y"], base-300],
                      [eje["x"], eje["y"], eje["z"]+500]]
            ids_nodos = [eje["nodo"]]
        else:
            puntos = eje["puntos_directriz"]
            ids_nodos = eje["nodos"]
        obj = doc.addObject("Part::Feature", "EJE_"+_nombre(eje["id"]))
        obj.Label = f"Eje {eje.get('nombre',eje['id'])} · {eje['id']}"
        obj.Shape = Part.makePolygon([App.Vector(*p) for p in puntos])
        if obj.Shape.isNull() or not obj.Shape.isValid() or obj.Shape.Solids:
            raise ValueError(f"{eje['id']}: eje de referencia inválido")
        _identidad(obj, datos["proyecto"], "eje", eje["id"], eje, ids_nodos,
                   referencias[eje["id"]], material=None)
        _prop(obj, "App::PropertyString", "TipoEje", eje["tipo"])
        _prop(obj, "App::PropertyString", "NombreEje", eje.get("nombre", eje["id"]))
        _prop(obj, "App::PropertyBool", "ReferenciaGeometrica", True)
        _prop(obj, "App::PropertyBool", "IncluidoEnCantidades", False)
        _prop(obj, "App::PropertyString", "RevisionParametros", revision)
        _prop(obj, "App::PropertyLinkList", "NodosVinculados", [anclas[n] for n in ids_nodos])
        _prop(obj, "App::PropertyLinkList", "TramosVinculados",
              [por_id[("tramo", t)] for t in eje.get("tramos", [])])
        _prop(obj, "App::PropertyString", "EstacionesResueltasJSON", json.dumps(
            {"unidades":"mm", "estaciones":eje.get("estaciones", [eje] if apoyo else [])},
            ensure_ascii=False))
        if not apoyo:
            _prop(obj, "App::PropertyLength", "LongitudEnPlanta", eje["longitud_mm"])
        _prop(obj, "App::PropertyString", "Representacion",
              "Marcador vertical del apoyo; extensión gráfica" if apoyo else
              "Directriz por nodos; la rasante detallada se conserva en la elevación")
        grupo.addObject(obj)
        if App.GuiUp:
            obj.ViewObject.LineColor = (0.72,0.38,0.12) if apoyo else (0.08,0.42,0.68)
            obj.ViewObject.LineWidth = 1.5 if apoyo else 2.0
            obj.ViewObject.DrawStyle = "Dashdot"
        objetos.append(obj)
    return objetos


def _perfil_elevacion(segmento, familias):
    """Contorno (estación, cota) útil, con los mismos peldaños del sólido."""
    rasante, cantos = segmento["puntos_rasante"], segmento["perfil_canto"]
    estaciones = sorted({p["estacion_mm"] for p in rasante+cantos})
    superior = [(s, _interpolar(rasante,s,"estacion_mm","z_mm")) for s in estaciones]
    inferior = [(s,z-_interpolar(cantos,s,"estacion_mm","canto_mm")) for s,z in superior]
    familia = familias[segmento["familia"]]
    if familia.get("tipo") == "escalera":
        a,b = superior[0],superior[-1]
        if a[1] > b[1]:
            a,b = b,a
        numero = familia["numero_peldanos"]
        ds,dz = (b[0]-a[0])/numero,(b[1]-a[1])/numero
        superior = [a]
        for i in range(numero):
            superior.extend([(a[0]+i*ds,a[1]+(i+1)*dz),
                             (a[0]+(i+1)*ds,a[1]+(i+1)*dz)])
        if ds < 0:
            superior.reverse()
    return superior,inferior


def _svg_elevacion(eje, familias, proyecto, revision):
    """Vista derivada y trazable; no es una proyección TechDraw asociativa.

    Usa distancias acumuladas en planta. La escala X/Z es idéntica. Los apoyos
    son trazas de sus ejes y cotas, no siluetas inventadas de dados compartidos.
    """
    estaciones = eje["estaciones"]
    perfiles = [(s, *_perfil_elevacion(s, familias)) for s in eje["segmentos"]]
    niveles = [p[1] for _,sup,inf in perfiles for p in sup+inf]
    niveles += [p["z"] for p in estaciones]
    niveles += [f[k] for p in estaciones for f in p.get("fundaciones", [])
                for k in ("cota_superior_mm", "cota_inferior_mm")]
    niveles += [s["cota_terreno_proyectado_mm"] for p in estaciones for s in p.get("soportes", [])
                if "cota_terreno_proyectado_mm" in s]
    zmin,zmax = min(niveles),max(niveles)
    alto_real = max(zmax-zmin,1000)
    longitud = eje["longitud_mm"]
    escala = min(1050/max(longitud,1),270/alto_real)
    izquierda = 120+(1050-longitud*escala)/2
    x = lambda s: izquierda+s*escala
    y = lambda z: 220+(zmax-z)*escala
    metros = lambda mm: f"{mm/1000:.3f}"
    ancho, alto = 1300, 734+len(estaciones)*30
    desarrollada = not eje["es_recto"]
    vista = "ELEVACIÓN DESARROLLADA" if desarrollada else "ELEVACIÓN LONGITUDINAL"
    rotulo = f"{vista} · {eje['id']} · {eje.get('nombre',eje['id'])}"
    lineas = [f'<svg xmlns="http://www.w3.org/2000/svg" width="420mm" height="{420*alto/ancho:.2f}mm" viewBox="0 0 {ancho} {alto}">',
              f'<title>{escape(rotulo)}</title>',
              '<desc>Vista conceptual derivada del modelo. Metros. Escala horizontal y vertical idéntica. Estaciones acumuladas en planta.</desc>',
              '<style>text{font-family:Arial,sans-serif;fill:#243746;font-size:14px} .muted{fill:#637481;font-size:12px}.grid{stroke:#e3e9ed;stroke-width:1}.axis{stroke:#b57135;stroke-width:1;stroke-dasharray:7 3 1 3}.dim{stroke:#607580;stroke-width:1}.small{font-size:12px}.level{font-size:12px;fill:#10728a}</style>',
              '<rect width="100%" height="100%" fill="white"/>',
              '<rect x="28" y="25" width="1244" height="5" fill="#176f85"/>']

    def texto(xx, yy, valor, clase="", ancla="start", extra=""):
        lineas.append(f'<text x="{xx:.3f}" y="{yy:.3f}" class="{clase}" text-anchor="{ancla}" {extra}>{escape(str(valor))}</text>')

    def linea(x1,y1,x2,y2,clase="dim",extra=""):
        lineas.append(f'<line x1="{x1:.3f}" y1="{y1:.3f}" x2="{x2:.3f}" y2="{y2:.3f}" class="{clase}" {extra}/>')

    def puntos_svg(puntos):
        return " ".join(f"{x(s):.4f},{y(z):.4f}" for s,z in puntos)

    texto(35,61,rotulo,extra='style="font-size:22px;font-weight:bold"')
    texto(35,85,f"{proyecto['nombre']} · Conceptual · Revisión de parámetros {revision}","muted")
    texto(35,106,"Cotas y distancias en m · Estaciones acumuladas en planta · Sin exageración vertical", "muted")
    lineas.append('<metadata>'+escape(json.dumps({"eje":eje["id"],"uuid_eje":eje.get("uuid"),
        "revision_parametros":revision,"tipo_vista":"desarrollada" if desarrollada else "longitudinal",
        "unidades":"m","estaciones":[{"nodo":p["nodo"],"estacion_m":p["estacion_mm"]/1000,"cota_m":p["z"]/1000}
                                                   for p in estaciones]},ensure_ascii=False))+'</metadata>')
    # Retícula de cotas: intervalos legibles 1, 2, 5 por potencia de diez.
    bruto = alto_real/5
    potencia = 10**math.floor(math.log10(bruto))
    paso = next(v*potencia for v in (1,2,5,10) if v*potencia >= bruto)
    inicio = math.ceil(zmin/paso)*paso
    for i in range(8):
        z = inicio+i*paso
        if z > zmax+1e-6:
            break
        linea(100,y(z),1190,y(z),"grid")
        texto(90,y(z)+4,metros(z),"muted","end")
    texto(37,198,"Cota [m]","muted")
    cajas_rotulos = []
    for numero,(seg,sup,inf) in enumerate(perfiles):
        lineas.append(f'<g id="tramo-{numero+1}-{_nombre(seg["tramo"])}">')
        lineas.append(f'<polygon points="{puntos_svg(sup+list(reversed(inf)))}" fill="#dce7eb" stroke="#395b69" stroke-width="1.5"/>')
        # La referencia de paso es independiente del contorno de peldaños.
        if familias[seg["familia"]].get("tipo") == "escalera":
            ref = [(p["estacion_mm"],p["z_mm"]) for p in seg["puntos_rasante"]]
            lineas.append(f'<polyline points="{puntos_svg(ref)}" fill="none" stroke="#16829a" stroke-width="1" stroke-dasharray="4 3"/>')
        sx = (seg["estacion_inicio_util_mm"]+seg["estacion_fin_util_mm"])/2
        zz = _interpolar(seg["puntos_rasante"],sx,"estacion_mm","z_mm")
        rx,ry,ancho_rotulo = x(sx),y(zz)-12,max(18,len(seg["tramo"])*7)
        caja = lambda yy: (rx-ancho_rotulo/2,yy-13,rx+ancho_rotulo/2,yy+3)
        def ocupa(yy):
            a = caja(yy)
            return any(a[0] < b[2]+5 and a[2]+5 > b[0] and a[1] < b[3]+3 and a[3]+3 > b[1]
                       for b in cajas_rotulos)
        if ocupa(ry):
            # Los retornos cortos suelen tener identificadores largos. Bajar
            # su rótulo evita tapar los tramos vecinos y los globos de estación.
            canto = _interpolar(seg["perfil_canto"],sx,"estacion_mm","canto_mm")
            ry = y(zz-canto)+22
            while ocupa(ry):
                ry += 19
            linea(rx,y(zz-canto)+2,rx,ry-14,"grid")
        cajas_rotulos.append(caja(ry))
        texto(rx,ry,seg["tramo"],"small","middle")
        lineas.append('</g>')
    for i,p in enumerate(estaciones):
        xx = x(p["estacion_mm"])
        marcadores = p.get("ejes_apoyo", [])
        eje_id = marcadores[0]["id"] if marcadores else "nodo-"+p["nodo"]
        # Una marca por apoyo, incluso cuando el dado pertenece a varios nodos.
        lineas.append(f'<g id="marca-{i+1}-{_nombre(eje_id)}">')
        burbuja = 137+(i%3)*23
        linea(xx,burbuja+10,xx,500,"axis" if marcadores else "grid")
        lineas.append(f'<circle cx="{xx:.3f}" cy="{burbuja}" r="10" fill="white" stroke="#b57135"/>')
        texto(xx,burbuja+4,i+1,"small","middle")
        lineas.append(f'<circle cx="{xx:.3f}" cy="{y(p["z"]):.3f}" r="3" fill="#176f85"/>')
        for soporte in p.get("soportes", []):
            yy = y(soporte["cota_superior_mm"])
            linea(xx-7,yy,xx+7,yy,extra='stroke="#10728a" stroke-width="2"')
            if "cota_terreno_proyectado_mm" in soporte:
                zt = soporte["cota_terreno_proyectado_mm"]
                yt = y(zt)
                sid = escape(str(soporte["id"]), {'"': '&quot;'})
                nid = escape(str(p["nodo"]), {'"': '&quot;'})
                lineas.append(f'<g class="projected-terrain-level" data-support-id="{sid}" data-node-id="{nid}" data-z-mm="{zt}">')
                linea(xx-11,yt,xx+11,yt,extra='stroke="#637847" stroke-width="1.5"')
                lineas.append(f'<circle cx="{xx:.3f}" cy="{yt:.3f}" r="3" fill="white" stroke="#637847"/>')
                texto(xx,yt-10,f"Terreno proyectado {metros(zt)} m","small","middle",'style="fill:#52643e;paint-order:stroke;stroke:white;stroke-width:3px;stroke-linejoin:round"')
                lineas.append('</g>')
        for dado in p.get("fundaciones", []):
            for k in ("cota_superior_mm", "cota_inferior_mm"):
                yy = y(dado[k])
                linea(xx-9,yy,xx+9,yy,extra='stroke="#10728a"')
        lineas.append('</g>')
        linea(xx,518,xx,549)
    for a,b in zip(estaciones,estaciones[1:]):
        xa,xb = x(a["estacion_mm"]),x(b["estacion_mm"])
        linea(xa,535,xb,535)
        for xx in (xa,xb):
            linea(xx-3,538,xx+3,532)
        if xb-xa >= 48:
            texto((xa+xb)/2,530,metros(b["estacion_mm"]-a["estacion_mm"]),"small","middle")
    linea(x(0),572,x(longitud),572)
    for xx in (x(0),x(longitud)):
        linea(xx,560,xx,579)
    texto((x(0)+x(longitud))/2,567,f"Longitud en planta: {metros(longitud)} m","small","middle")
    texto(35,608,"Los números remiten a la tabla. Δ indica la distancia entre estaciones; incluye los intervalos cortos.","muted")
    texto(35,627,"Apoyos: ejes y cotas declaradas. Terreno proyectado: niveles puntuales al centro de cada apoyo; no define una superficie.","muted")
    columnas = (43,83,265,470,590,735,895,1080)
    titulos = ("N°","Nodo / tipo","Eje de apoyo","Estación [m]","Δ anterior [m]","Paso [m]","Cima apoyo [m]","Dado sup. / inf. [m]")
    lineas.append('<rect x="28" y="651" width="1244" height="31" fill="#eaf1f4"/>')
    for xx,titulo in zip(columnas,titulos):
        texto(xx,672,titulo,"small")
    for i,p in enumerate(estaciones):
        yy = 705+i*30
        tipo = {"columna":"cepa","estribo":"estribo","encuentro":"encuentro"}.get(p["tipo_nodo"],p["tipo_nodo"])
        apoyos = ", ".join(a["id"] for a in p.get("ejes_apoyo", [])) or "—"
        soporte = ", ".join(metros(a["cota_superior_mm"]) for a in p.get("soportes", [])) or "—"
        fundacion = "; ".join(metros(a["cota_superior_mm"])+" / "+metros(a["cota_inferior_mm"])
                               for a in p.get("fundaciones", [])) or "—"
        valores = (i+1,p["nodo"]+" / "+tipo,apoyos,metros(p["estacion_mm"]),
                   metros(p["estacion_mm"]-estaciones[i-1]["estacion_mm"]) if i else "—",
                   metros(p["z"]),soporte,fundacion)
        for xx,valor in zip(columnas,valores):
            texto(xx,yy,valor,"small")
        linea(28,yy+10,1272,yy+10,"grid")
    texto(35,alto-16,"Vista derivada de parámetros: regenerar al editar el proyecto. No sustituye planos de detalle ni comprobación estructural.","muted")
    lineas.append('</svg>')
    return "\n".join(lineas)


def _crear_elevaciones(datos, portable, salida, revision):
    archivos = []
    for eje in datos.get("ejes_resueltos", []):
        if eje["tipo"] == "apoyo":
            continue
        # El índice evita colisiones entre identificadores válidos que se
        # normalizan igual para un nombre de archivo (p. ej. AX-1 y AX_1).
        ruta = salida/f"elevacion_{len(archivos)+1:02d}_{_nombre(eje['id'])}.svg"
        ruta.write_text(_svg_elevacion(eje, datos["familias"], portable["proyecto"], revision),encoding="utf-8")
        archivos.append(str(ruta))
    return archivos


def generar(modelo, carpeta_salida, con_vistas=True):
    """Genera FCStd, cantidades y verificación. Requiere Python de FreeCAD.

    ``con_vistas`` crea TechDraw únicamente si existe una sesión GUI. Las
    elevaciones SVG derivadas de ejes no requieren GUI y se exportan siempre.
    No inicia aplicaciones ni instala paquetes; deja abierto el FCStd verificado.
    """
    import FreeCAD as App
    import Part
    from .topologia import resolver_modelo
    from .proyecto import convertir_a_portable

    datos = resolver_modelo(modelo)
    portable = convertir_a_portable(modelo)
    revision = hashlib.sha256(json.dumps(portable,ensure_ascii=False,sort_keys=True,
                                        separators=(",", ":")).encode("utf-8")).hexdigest()[:16]
    parametros_portables = {rol: {p["id"]: p for p in portable.get(coleccion, [])}
                           for rol, coleccion in (("nodo", "nodos"), ("tramo", "tramos"),
                                                  ("dado", "fundaciones"), ("soporte", "soportes"))}
    parametros_portables["pilote"] = {p["id"]: p for f in portable.get("fundaciones", [])
                                      for p in f.get("pilotes", [])}
    proyecto = datos["proyecto"]
    salida = Path(carpeta_salida).resolve()
    salida.mkdir(parents=True, exist_ok=True)
    nodos = datos["nodos_por_id"]
    familias = datos["familias"]
    avisos = ["Geometría conceptual regenerada desde parámetros; no dimensiona la estructura.",
              "Capiteles y estribos simplificados; sin apoyos elastoméricos ni armaduras.",
              "El espesor de alma del cajón se representa en dirección horizontal."]
    avisos.extend(a["mensaje"] for a in datos["validacion"].get("avisos",[]))
    doc = App.newDocument("Pasarela_"+_nombre(proyecto["id"]))
    doc.Label = proyecto["nombre"]+" - conceptual"
    _prop(doc, "App::PropertyString", "ConfiguracionPasarelaJSON",
          json.dumps(portable, ensure_ascii=False))
    _prop(doc, "App::PropertyString", "EstadoModelo", "conceptual")
    _prop(doc, "App::PropertyString", "RevisionParametros", revision)
    georreferencia = proyecto.get("georreferencia",datos.get("georreferencia"))
    if georreferencia:
        _prop(doc,"App::PropertyString","GeorreferenciaJSON",json.dumps(georreferencia,ensure_ascii=False))
    grupos = {rol: doc.addObject("App::DocumentObjectGroup", nombre) for rol, nombre in (
        ("nodo", "Topologia"), ("tramo", "Superestructura"),
        ("dado", "Fundaciones"), ("pilote", "Pilotes"),
        ("soporte", "Soportes"), ("capitel", "CapitelesConceptuales"))}
    objetos, anclas, por_id = [], {}, {}

    def materializar(rol, identificador, shape, parametros, ids_nodos=()):
        obj = doc.addObject("Part::Feature", rol.upper()+"_"+_nombre(identificador))
        obj.Label = f"{rol.capitalize()} {identificador}"
        obj.Shape = shape
        _validar_shape(obj)
        _identidad(obj, proyecto, rol, identificador, parametros, ids_nodos,
                   parametros_portables.get(rol, {}).get(identificador, parametros))
        _prop(obj, "App::PropertyLinkList", "NodosVinculados",
              [anclas[i] for i in ids_nodos if i in anclas])
        _prop(obj, "App::PropertyString", "Simplificacion",
              "Bloque/cuñas conceptuales" if rol in ("capitel", "soporte") else
              "Sólido conceptual definido por parámetros")
        grupos[rol].addObject(obj)
        if App.GuiUp:
            colores = {"tramo": (0.72,0.79,0.83), "dado": (0.61,0.65,0.69),
                       "pilote": (0.73,0.73,0.73), "soporte": (0.82,0.83,0.79),
                       "capitel": (0.92,0.75,0.45)}
            obj.ViewObject.ShapeColor = colores[rol]
            obj.ViewObject.LineColor = (0.15,0.18,0.22)
        objetos.append(obj)
        por_id[(rol, str(identificador))] = obj
        return obj

    for nodo in datos["nodos"]:
        obj = doc.addObject("App::FeaturePython", "NODO_"+_nombre(nodo["id"]))
        obj.Label = "Nodo "+nodo["id"]
        _identidad(obj, proyecto, "nodo", nodo["id"], nodo,
                   parametros_portables=parametros_portables["nodo"][nodo["id"]])
        _prop(obj, "App::PropertyVector", "CoordenadaPaso", App.Vector(nodo["x"],nodo["y"],nodo["z"]))
        grupos["nodo"].addObject(obj)
        anclas[nodo["id"]] = obj
    for fundacion in datos["fundaciones"]:
        x, y, z = fundacion["centro"]
        alto = float(fundacion["alto_mm"])
        obj_dado = materializar("dado", fundacion["id"], _bloque(
            Part, App, fundacion["largo_mm"], fundacion["ancho_mm"], alto,
            x, y, z-alto, fundacion["angulo_deg"]), fundacion, fundacion["nodos"])
        for pilote in fundacion.get("pilotes", []):
            px, py, pz = pilote["centro"]
            shape = Part.makeCylinder(pilote["diametro_mm"]/2, pilote["longitud_mm"],
                                      App.Vector(px,py,pz), App.Vector(0,0,-1))
            obj_p = materializar("pilote", pilote["id"], shape, pilote, fundacion["nodos"])
            _prop(obj_p, "App::PropertyLink", "FundacionVinculada", obj_dado)
    for tramo in datos["tramos"]:
        familia = familia_del_tramo(familias[tramo["familia"]], tramo, nodos)
        ala_efectiva = (tramo["ancho_mm"]-familia.get("ancho_alma_superior_mm",tramo["ancho_mm"]))/2
        if abs(ala_efectiva-familia.get("ala_mm", ala_efectiva)) > 0.01:
            avisos.append(f"{tramo['id']}: ala efectiva {ala_efectiva:g} mm según ancho total del tramo.")
        obj = materializar("tramo", tramo["id"], _tramo_shape(Part,App,tramo,familia,nodos),
                           tramo, [tramo["desde"],tramo["hasta"]])
        _prop(obj,"App::PropertyString","FamiliaSeccion",tramo["familia"])
        _prop(obj,"App::PropertyLength","AlaEfectiva",ala_efectiva)
        _prop(obj,"App::PropertyLength","LongitudEnPlanta",tramo["longitud_planta_mm"])
        _prop(obj,"App::PropertyLength","LongitudPiezaEnPlanta",tramo["longitud_util_mm"])
        _prop(obj,"App::PropertyString","PerfilCantoJSON",json.dumps(
            [{"t": p["t"], "canto_m": p["canto_mm"]/1000} for p in _perfil_canto(familia)]))
        _prop(obj,"App::PropertyString","FuncionTramo",tramo.get("funcion",tramo["tipo"]))
        if familia.get("tipo") == "escalera":
            _prop(obj,"App::PropertyInteger","NumeroPeldanos",familia["numero_peldanos"])
            _prop(obj,"App::PropertyLength","Huella",tramo["huella_mm"])
            _prop(obj,"App::PropertyLength","Contrahuella",tramo["contrahuella_mm"])
    recortes = []
    # Prioridad geométrica genérica: conservar primero la viga de mayor canto;
    # luego la de mayor longitud y, ante empate, el identificador estable.
    vigas_ordenadas = sorted((t for t in datos["tramos"] if t["tipo"] == "viga"),
        key=lambda t:(-max(p["canto_mm"] for p in _perfil_canto(familias[t["familia"]])),
                      -t["longitud_planta_mm"],t["id"]))
    anteriores = []
    for tramo in vigas_ordenadas:
        extremos = {tramo["desde"],tramo["hasta"]}
        cortantes = [por_id[("tramo", t["id"])] for t in anteriores
                    if extremos.intersection((t["desde"],t["hasta"]))]
        obj = por_id[("tramo",tramo["id"])]
        volumen = _recortar_encuentro(obj,cortantes)
        if volumen > 1000:
            recortes.append({"objeto":obj.Name,"volumen_recortado_m3":round(volumen/1e9,8),
                             "pares":json.loads(obj.RecorteEncuentroJSON)["pares"]})
        anteriores.append(tramo)
    for tramo in datos["tramos"]:
        if tramo["tipo"] != "retorno":
            continue
        extremos = {tramo["desde"],tramo["hasta"]}
        vigas = [por_id[("tramo", t["id"])] for t in datos["tramos"]
                 if t["tipo"] == "viga" and extremos.intersection((t["desde"],t["hasta"]))]
        obj = por_id[("tramo",tramo["id"])]
        volumen = _recortar_encuentro(obj,vigas)
        recortes.append({"objeto":obj.Name,"volumen_recortado_m3":round(volumen/1e9,8),
                         "pares":json.loads(obj.RecorteEncuentroJSON)["pares"]})
    for soporte in datos["soportes"]:
        nodo = nodos[soporte["nodo"]]
        x,y,z = soporte["centro"]
        alto = soporte["altura_mm"]
        fundacion = next(f for f in datos["fundaciones"] if f["id"] == soporte["fundacion"])
        if nodo["tipo"] == "estribo":
            shape = _bloque(Part,App,soporte.get("largo_mm",1200),
                            soporte.get("ancho_mm",2200),alto,x,y,z,fundacion["angulo_deg"])
        else:
            shape = Part.makeCylinder(soporte["diametro_mm"]/2,alto,App.Vector(x,y,z))
        parametros_soporte = dict(soporte)
        if not parametros_soporte.get("uuid") and nodo.get("uuid"):
            parametros_soporte["uuid"] = nodo["uuid"]
        obj_s = materializar("soporte",soporte["id"],shape,parametros_soporte,[nodo["id"]])
        _prop(obj_s,"App::PropertyLink","FundacionVinculada",por_id[("dado",soporte["fundacion"])])
        if "cota_terreno_proyectado_mm" in soporte:
            cota_terreno = soporte["cota_terreno_proyectado_mm"]
            _prop(obj_s,"App::PropertyDistance","CotaTerrenoProyectado",cota_terreno,"Terreno proyectado")
            _prop(obj_s,"App::PropertyVector","CentroTerrenoProyectado",
                  App.Vector(nodo["x"],nodo["y"],cota_terreno),"Terreno proyectado")
            _prop(obj_s,"App::PropertyString","ReferenciaTerrenoProyectado",
                  "Cota local proyectada en el centro del apoyo; no define una superficie ni modifica la fundación.",
                  "Terreno proyectado")
        conectados = [t for t in datos["tramos"] if nodo["id"] in (t["desde"],t["hasta"])]
        shape_cap = _capitel_shape(Part,App,soporte,nodo,conectados,familias,nodos)
        if shape_cap is not None:
            parametros_cap = {"fuente":"Aproximación geométrica; no reproduce el molde de referencia"}
            if nodo.get("uuid"):
                parametros_cap["uuid"] = nodo["uuid"]
            cap = materializar("capitel",nodo["id"],shape_cap,parametros_cap,[nodo["id"]])
            _prop(cap,"App::PropertyLink","SoporteVinculado",obj_s)
            _prop(cap,"App::PropertyLinkList","TramosVinculados",
                  [por_id[("tramo",t["id"])] for t in conectados])
            volumen = _recortar_encuentro(cap,list(cap.TramosVinculados))
            if volumen > 1000:
                recortes.append({"objeto":cap.Name,"volumen_recortado_m3":round(volumen/1e9,8),
                                 "pares":json.loads(cap.RecorteEncuentroJSON)["pares"]})
        else:
            avisos.append(f"{nodo['id']}: capitel omitido, sin altura positiva entre soporte e intradós.")
    for identificador, ancla in anclas.items():
        # El enlace inverso es informativo: un PropertyLinkList aquí produciría
        # un ciclo nodo->elemento->nodo en el grafo de recomputación de FreeCAD.
        _prop(ancla,"App::PropertyStringList","ElementosConectados",
              [o.Name for o in objetos if identificador in o.NodosTopologicos])
    ejes_referencia = _crear_ejes(doc,Part,App,datos,portable,anclas,por_id,revision)
    doc.recompute()
    solapes = _solapes(objetos)
    if solapes:
        avisos.append(f"{len(solapes)} intersecciones volumétricas pendientes; las sumas por pieza pueden duplicar volumen.")
    antes = {o.Name:{"uuid":o.UUIDBIM,"volumen_mm3":_validar_shape(o)} for o in objetos}
    antes_nodos = {o.Name:o.UUIDBIM for o in anclas.values()}
    antes_ejes = {o.Name:{"uuid":o.UUIDBIM,"id":o.IDTopologico,"tipo":o.TipoEje,
                         "tramos":[t.Name for t in o.TramosVinculados],
                         "vertices":[(v.Point.x,v.Point.y,v.Point.z) for v in o.Shape.Vertexes]}
                  for o in ejes_referencia}
    archivos_vistas = _crear_vistas(doc,objetos,salida,proyecto["nombre"],avisos) if con_vistas else []
    archivos_elevaciones = _crear_elevaciones(datos,portable,salida,revision)
    archivos_vistas.extend(archivos_elevaciones)
    ruta_fcstd = salida/("pasarela_"+_nombre(proyecto["id"])+".FCStd")
    doc.recompute()
    doc.saveAs(str(ruta_fcstd))
    nombre_doc = doc.Name
    App.closeDocument(nombre_doc)
    reabierto = App.openDocument(str(ruta_fcstd))
    for nombre, referencia in antes.items():
        obj = reabierto.getObject(nombre)
        if obj is None or obj.UUIDBIM != referencia["uuid"]:
            raise ValueError(f"Persistencia: identidad perdida en {nombre}")
        volumen = _validar_shape(obj)
        if abs(volumen-referencia["volumen_mm3"]) > max(1.0,volumen*1e-8):
            raise ValueError(f"Persistencia: cambió el volumen de {nombre}")
    for nombre, identificador in antes_nodos.items():
        if reabierto.getObject(nombre).UUIDBIM != identificador:
            raise ValueError(f"Persistencia: identidad perdida en {nombre}")
    for nombre, ref in antes_ejes.items():
        obj = reabierto.getObject(nombre)
        if (obj is None or obj.UUIDBIM != ref["uuid"] or obj.IDTopologico != ref["id"]
                or obj.TipoEje != ref["tipo"] or obj.RevisionParametros != revision
                or obj.IncluidoEnCantidades or "MaterialBIM" in obj.PropertiesList
                or [t.Name for t in obj.TramosVinculados] != ref["tramos"]):
            raise ValueError(f"Persistencia: referencia de eje perdida en {nombre}")
        vertices = [(v.Point.x,v.Point.y,v.Point.z) for v in obj.Shape.Vertexes]
        if (obj.Shape.isNull() or not obj.Shape.isValid() or obj.Shape.Solids
                or len(vertices) != len(ref["vertices"])
                or any(abs(a-b)>1e-6 for p,q in zip(vertices,ref["vertices"]) for a,b in zip(p,q))):
            raise ValueError(f"Persistencia: geometría de eje alterada en {nombre}")
    # Reapertura también debe conservar los vínculos topológicos, no solo texto.
    for obj in reabierto.Objects:
        if "NodosVinculados" in obj.PropertiesList and len(obj.NodosVinculados) != len(obj.NodosTopologicos):
            raise ValueError(f"Persistencia: conexiones incompletas en {obj.Name}")
    cantidades = []
    volumenes = defaultdict(float)
    for nombre in antes:
        obj = reabierto.getObject(nombre)
        volumen = obj.Shape.Volume/1e9
        volumenes[obj.RolBIM] += volumen
        cantidades.append({"id":obj.IDTopologico,"rol":obj.RolBIM,"uuid":obj.UUIDBIM,
                           "numero_solidos":len(obj.Shape.Solids),
                           "volumen_m3":round(volumen,6),"objeto_freecad":obj.Name})
    if any(c["numero_solidos"] > 1 for c in cantidades):
        avisos.append("Los recortes de encuentro dejan elementos compuestos por varias porciones; no se verifica su continuidad estructural.")
    pagina = reabierto.getObject("LAMINA_A1")
    vistas_persistidas = len(pagina.Views) if pagina is not None else 0
    if pagina is not None and (vistas_persistidas != 4 or
            any(set(o.Name for o in v.Source) != set(antes) for v in pagina.Views)):
        raise ValueError("Persistencia: vínculos incompletos en las vistas TechDraw")
    reporte = {"valido":True,"estado":"conceptual","proyecto":portable["proyecto"],
               "revision_parametros":revision,
               "archivo_fcstd":str(ruta_fcstd),"archivos_vistas":archivos_vistas,
               "archivos_elevaciones":archivos_elevaciones,
               "ejes":[{"id":r["id"],"uuid":r["uuid"],"tipo":r["tipo"],"objeto_freecad":nombre}
                       for nombre,r in antes_ejes.items()],
               "verificacion":{"elementos_validos":len(antes),
                               "solidos_validos":sum(c["numero_solidos"] for c in cantidades),
                               "ejes_referencia_conservados":len(antes_ejes),
                               "elevaciones_derivadas":len(archivos_elevaciones),
                               "vistas_asociativas_conservadas":vistas_persistidas,
                               "sin_solapes_mayores_1cm3":not solapes,
                               "guardado_y_reabierto":True,
                               "identidades_y_volumenes_conservados":True,"conexiones_conservadas":True},
               "conteos":dict(Counter(o["rol"] for o in cantidades)),"cantidades":cantidades,
               "volumenes_m3":{k:round(v,6) for k,v in volumenes.items()},"avisos":avisos,
               "recortes_encuentros":recortes,"solapes_pendientes":solapes,
               "comprobaciones":datos["validacion"].get("comprobaciones",[]),
               "limitaciones":["Sólidos regenerados; editar dimensiones exige regenerar desde configuración.",
                               "No se verifican resistencia, cimentación, normativa ni capacidad de los encuentros.",
                               "Cantidades geométricas conceptuales, no cubicación contractual."]}
    ruta_reporte = salida/"reporte_generacion.json"
    reporte["archivo_reporte"] = str(ruta_reporte)
    ruta_reporte.write_text(json.dumps(reporte,ensure_ascii=False,indent=2),encoding="utf-8")
    return reporte
