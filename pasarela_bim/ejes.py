"""Ejes por referencias topológicas y alzados desarrollados en milímetros.

El JSON intercambiable sólo guarda referencias, nombres e identidad. Estaciones,
directrices y perfiles se derivan sin modificar nodos, tramos ni cimentaciones.
"""

from collections import defaultdict
from copy import deepcopy
import math
import uuid

from .proyecto import convertir_a_interno


_ESPACIO = uuid.UUID("a7efdaec-e185-511b-843b-ec77e8199bda")
_LONGITUDINALES = {"atravieso", "recorrido"}


def _texto(valor):
    return isinstance(valor, str) and bool(valor.strip())


def _mapa(valores):
    return {v["id"]: v for v in valores if isinstance(v, dict) and _texto(v.get("id"))} if isinstance(valores, list) else {}


def _ids_entidades(modelo):
    ids = set()
    for coleccion in ("nodos","tramos","soportes","fundaciones"):
        ids.update(_mapa(modelo.get(coleccion)))
    for dado in _mapa(modelo.get("fundaciones")).values():
        ids.update(_mapa(dado.get("pilotes")))
    return ids


def nodos_de_cadena(eje, tramos):
    """Ordena los nodos siguiendo exactamente la lista ordenada de tramos.

    El sentido de un tramo aislado es desde→hasta. Con varios tramos se deduce
    del extremo común con el segundo; las orientaciones propias pueden diferir.
    Rechaza circuitos y ramificaciones dentro del propio eje.
    """
    refs = eje.get("tramos")
    if not isinstance(refs, list) or not refs or not all(_texto(i) for i in refs):
        raise ValueError("El eje necesita una lista no vacía de tramos ordenados")
    if len(set(refs)) != len(refs):
        raise ValueError("Un tramo no puede repetirse en el mismo eje")
    if any(i not in tramos for i in refs):
        raise ValueError("El eje refiere un tramo inexistente")
    piezas = [tramos[i] for i in refs]
    if any(not _texto(t.get("desde")) or not _texto(t.get("hasta")) or t["desde"] == t["hasta"] for t in piezas):
        raise ValueError("Los extremos de los tramos del eje deben ser nodos diferentes")
    primero = piezas[0]
    if len(piezas) == 1:
        return [primero["desde"], primero["hasta"]]
    comun = {primero["desde"], primero["hasta"]} & {piezas[1]["desde"], piezas[1]["hasta"]}
    if len(comun) != 1:
        raise ValueError("Los tramos del eje deben estar ordenados en una cadena continua")
    union = next(iter(comun))
    salida = [primero["hasta"] if primero["desde"] == union else primero["desde"], union]
    for tramo in piezas[1:]:
        if salida[-1] not in (tramo["desde"], tramo["hasta"]):
            raise ValueError("Los tramos del eje deben estar ordenados en una cadena continua")
        siguiente = tramo["hasta"] if tramo["desde"] == salida[-1] else tramo["desde"]
        if siguiente in salida:
            raise ValueError("Un eje no puede cerrar un circuito ni repetir un nodo")
        salida.append(siguiente)
    return salida


def _es_recto(puntos):
    if len(puntos) < 2:
        return True
    dx, dy = puntos[-1][0]-puntos[0][0], puntos[-1][1]-puntos[0][1]
    largo = math.hypot(dx,dy)
    if largo <= 1e-6:
        return False
    for p, q in zip(puntos,puntos[1:]):
        if abs(dx*(p[1]-puntos[0][1])-dy*(p[0]-puntos[0][0]))/largo > 0.001:
            return False
        if (q[0]-p[0])*dx+(q[1]-p[1])*dy <= 0:
            return False
    return True


def validar_ejes(modelo):
    """Incidencias de referencias; las coberturas incompletas son pendientes.

    Acepta v1/v2 sin exigir que el resto del proyecto esté terminado. La ausencia
    completa de ejes conserva compatibilidad legacy mediante un aviso.
    """
    errores, pendientes, avisos = [], [], []
    def agregar(lista,codigo,elemento,mensaje):
        lista.append({"codigo":codigo,"elemento":str(elemento),"mensaje":mensaje})
    resultado = {"errores":errores,"pendientes":pendientes,"avisos":avisos}
    if "ejes" not in modelo:
        agregar(avisos,"ejes_legacy_sin_definir","ejes","Proyecto sin ejes explícitos; no se han creado ni inferido automáticamente")
        return resultado
    ejes = modelo["ejes"]
    if not isinstance(ejes,list):
        agregar(errores,"ejes_invalidos","ejes","ejes debe ser una lista")
        return resultado
    nodos,tramos = _mapa(modelo.get("nodos")),_mapa(modelo.get("tramos"))
    ids_entidades = _ids_entidades(modelo)
    ids, uuids, propietarios, marcadores = set(),set(),defaultdict(list),defaultdict(list)
    principales = []
    for eje in ejes:
        if not isinstance(eje,dict):
            agregar(errores,"eje_invalido","ejes","Cada eje debe ser un objeto")
            continue
        identificador = eje.get("id","ejes")
        if not _texto(eje.get("id")) or eje.get("id") in ids or eje.get("id") in ids_entidades:
            agregar(errores,"id_eje_invalido",identificador,"El identificador del eje debe ser texto único en el proyecto")
        elif _texto(eje.get("id")):
            ids.add(eje["id"])
        if not _texto(eje.get("nombre")):
            agregar(errores,"nombre_eje_invalido",identificador,"El eje necesita un nombre visible")
        if "uuid" in eje:
            if not _texto(eje["uuid"]) or eje["uuid"] in uuids:
                agregar(errores,"uuid_eje_invalido",identificador,"La identidad uuid del eje debe ser texto único")
            else:
                uuids.add(eje["uuid"])
        tipo = eje.get("tipo")
        if not _texto(tipo) or tipo not in _LONGITUDINALES | {"apoyo"}:
            agregar(errores,"tipo_eje_invalido",identificador,"El tipo de eje debe ser atravieso, recorrido o apoyo")
            continue
        if "principal" in eje and type(eje["principal"]) is not bool:
            agregar(errores,"principal_eje_invalido",identificador,"principal debe ser booleano")
        if eje.get("principal") is True:
            if tipo != "atravieso":
                agregar(errores,"principal_eje_invalido",identificador,"Sólo un eje de atravieso puede ser principal")
            principales.append(identificador)
        if tipo == "apoyo":
            nodo = eje.get("nodo")
            if not _texto(nodo) or nodo not in nodos:
                agregar(errores,"nodo_eje_inexistente",identificador,"El eje de apoyo refiere un nodo inexistente")
            elif nodos[nodo].get("tipo") not in ("columna","estribo"):
                agregar(errores,"tipo_nodo_eje_apoyo",identificador,"El eje de apoyo debe referir una columna o un estribo")
            else:
                marcadores[nodo].append(identificador)
            if "tramos" in eje:
                agregar(errores,"referencias_eje_incompatibles",identificador,"Un eje de apoyo usa nodo, no una cadena de tramos")
            continue
        if "nodo" in eje:
            agregar(errores,"referencias_eje_incompatibles",identificador,"Un eje longitudinal usa tramos, no un nodo de apoyo")
        refs = eje.get("tramos")
        if isinstance(refs,list):
            for ref in refs:
                if _texto(ref) and ref in tramos:
                    propietarios[ref].append(identificador)
                    funcion = tramos[ref].get("funcion")
                    if _texto(funcion) and (tipo == "atravieso") != (funcion == "cruce"):
                        agregar(errores,"funcion_eje_incompatible",identificador,
                                f"El tramo {ref} no corresponde al tipo de eje {tipo}")
        try:
            cadena = nodos_de_cadena(eje,tramos)
            if any(n not in nodos for n in cadena):
                raise ValueError("La cadena refiere un nodo inexistente")
            if tipo == "atravieso":
                puntos = [[nodos[n].get(k) for k in "xy"] for n in cadena]
                if all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for p in puntos for v in p):
                    # Tolerancia fija en mm, también al validar directamente v2.
                    escala = 1000 if modelo.get("version") == 2 else 1
                    if not _es_recto([[v*escala for v in p] for p in puntos]):
                        agregar(errores,"atravieso_no_recto",identificador,"El eje de atravieso debe ser una cadena recta en planta")
        except ValueError as exc:
            agregar(errores,"cadena_eje_invalida",identificador,str(exc))
    if len(principales) > 1:
        agregar(errores,"varios_ejes_principales","ejes","Sólo puede existir un eje de atravieso principal")
    for ref in tramos:
        if len(propietarios[ref]) > 1:
            agregar(errores,"tramo_varios_ejes",ref,"Un tramo sólo puede pertenecer a un eje longitudinal")
        elif not propietarios[ref]:
            agregar(pendientes,"tramo_sin_eje",ref,"El tramo aún no tiene un eje longitudinal")
    for ref,nodo in nodos.items():
        if nodo.get("tipo") not in ("columna","estribo"):
            continue
        if len(marcadores[ref]) > 1:
            agregar(errores,"nodo_varios_ejes_apoyo",ref,"Cada columna o estribo tiene un único eje de apoyo")
        elif not marcadores[ref]:
            agregar(pendientes,"nodo_sin_eje_apoyo",ref,"La columna o estribo aún no tiene eje de apoyo")
    return resultado


def autoconstruir_ejes(modelo):
    """Devuelve una copia con ejes completos, preservando identidades existentes.

    Extiende cadenas sólo por sus extremos no bifurcados. Nunca fusiona dos
    ejes existentes. Los circuitos se dividen en cadenas abiertas; los cambios
    de rumbo de un atravieso también separan ejes rectos.
    """
    salida = deepcopy(modelo)
    ejes = salida.setdefault("ejes",[])
    incidencias = validar_ejes(salida)
    if incidencias["errores"]:
        raise ValueError("No se pueden completar ejes inválidos: "+"; ".join(e["mensaje"] for e in incidencias["errores"]))
    nodos,tramos = _mapa(salida.get("nodos")),_mapa(salida.get("tramos"))
    elegibles = {i:t for i,t in tramos.items() if _texto(t.get("desde")) and _texto(t.get("hasta"))
                 and t["desde"] in nodos and t["hasta"] in nodos and t["desde"] != t["hasta"]}
    clasificacion = {i:"atravieso" if t.get("funcion") == "cruce" else "recorrido" for i,t in elegibles.items()}
    vecinos = {tipo:defaultdict(list) for tipo in _LONGITUDINALES}
    for ref,t in elegibles.items():
        for n in (t["desde"],t["hasta"]):
            vecinos[clasificacion[ref]][n].append(ref)
    usados = {ref for eje in ejes if eje.get("tipo") in _LONGITUDINALES for ref in eje["tramos"]}
    ids = _ids_entidades(salida)|{e["id"] for e in ejes}
    proyecto = salida.get("proyecto",{})
    semilla = str(proyecto.get("uuid",proyecto.get("id","proyecto")))

    def crear(tipo,refs=None,nodo=None):
        prefijo = "EA" if tipo == "apoyo" else "AX"
        numero = 1
        while prefijo+str(numero) in ids:
            numero += 1
        identificador = prefijo+str(numero)
        ids.add(identificador)
        identidad = nodos[nodo].get("uuid",nodo) if nodo else ":".join(sorted(str(tramos[r].get("uuid",r)) for r in refs))
        nombre = "Apoyo "+nodo if nodo else ("Atravieso" if tipo == "atravieso" else "Recorrido")+" "+str(1+sum(e["tipo"]==tipo for e in ejes))
        eje = {"id":identificador,"uuid":str(uuid.uuid5(_ESPACIO,semilla+":"+tipo+":"+identidad)),"nombre":nombre,"tipo":tipo}
        eje.update({"nodo":nodo} if nodo else {"tramos":list(refs)})
        ejes.append(eje)
        return eje

    def admisible(tipo,refs):
        try:
            cadena = nodos_de_cadena({"tramos":refs},tramos)
            if tipo == "atravieso":
                factor = 1000 if salida.get("version") == 2 else 1
                return _es_recto([[nodos[n][k]*factor for k in "xy"] for n in cadena])
            return True
        except (ValueError,KeyError,TypeError):
            return False

    def extender(eje):
        tipo = eje["tipo"]
        cambio = True
        while cambio:
            cambio = False
            cadena = nodos_de_cadena(eje,tramos)
            for inicio,n in ((True,cadena[0]),(False,cadena[-1])):
                disponibles = [r for r in vecinos[tipo][n] if r not in usados]
                if len(vecinos[tipo][n]) != 2 or len(disponibles) != 1:
                    continue
                ref = disponibles[0]
                nueva = [ref]+eje["tramos"] if inicio else eje["tramos"]+[ref]
                if admisible(tipo,nueva):
                    eje["tramos"] = nueva
                    usados.add(ref)
                    cambio = True
                    break

    for eje in list(ejes):
        if eje["tipo"] in _LONGITUDINALES:
            extender(eje)
    for tipo in ("atravieso","recorrido"):
        pendientes = lambda: sorted(r for r in elegibles if clasificacion[r] == tipo and r not in usados)
        while pendientes():
            refs = pendientes()
            # Empezar cerca de un extremo/bifurcación evita partir cadenas simples.
            ref = next((r for r in refs if any(len(vecinos[tipo][n]) != 2 for n in (tramos[r]["desde"],tramos[r]["hasta"]))),refs[0])
            eje = crear(tipo,[ref])
            usados.add(ref)
            extender(eje)
    asignados = {e["nodo"] for e in ejes if e["tipo"] == "apoyo"}
    for ref,nodo in nodos.items():
        if nodo.get("tipo") in ("columna","estribo") and ref not in asignados:
            crear("apoyo",nodo=ref)
    if not any(e.get("principal") is True for e in ejes):
        principal = next((e for e in ejes if e["tipo"] == "atravieso"),None)
        if principal is not None:
            principal["principal"] = True
    return salida


def _interpolar(perfil,t,clave):
    for a,b in zip(perfil,perfil[1:]):
        if t <= b["t"]:
            return a[clave]+(b[clave]-a[clave])*(t-a["t"])/(b["t"]-a["t"])
    return perfil[-1][clave]


def resolver_ejes(modelo):
    """Deriva ejes y perfiles de un modelo geométrico ya validado, en mm.

    Estaciones: distancia acumulada EN PLANTA, no longitud inclinada. La rasante
    y el canto de cada pieza se recortan a sus retranqueos. Nunca se proyecta una
    vuelta en U sobre una única dirección: el alzado es desarrollado por cadena.
    """
    datos = convertir_a_interno(modelo)
    if "ejes" not in datos:
        return []
    incidencias = validar_ejes(datos)
    if incidencias["errores"] or incidencias["pendientes"]:
        raise ValueError("Ejes incompletos o inválidos: "+"; ".join(e["mensaje"] for e in incidencias["errores"]+incidencias["pendientes"]))
    nodos,tramos,dados = _mapa(datos.get("nodos")),_mapa(datos.get("tramos")),_mapa(datos.get("fundaciones"))
    marcadores,soportes = defaultdict(list),defaultdict(list)
    for eje in datos["ejes"]:
        if eje["tipo"] == "apoyo":
            marcadores[eje["nodo"]].append({k:eje[k] for k in ("id","nombre","uuid") if k in eje})
    for soporte in datos.get("soportes",[]):
        soportes[soporte["nodo"]].append(soporte)

    def estacion(ref,distancia):
        nodo = nodos[ref]
        ss = soportes[ref]
        fundaciones = [dados[i] for i in dict.fromkeys(s["fundacion"] for s in ss)]
        return {"nodo":ref,"tipo_nodo":nodo["tipo"],"estacion_mm":distancia,
                **{k:nodo[k] for k in "xyz"},"ejes_apoyo":deepcopy(marcadores[ref]),
                "soportes":[{k:s[k] for k in ("id","fundacion","cota_superior_mm","diametro_mm","ancho_mm","largo_mm") if k in s} for s in ss],
                "fundaciones":[{"id":f["id"],"cota_superior_mm":f["cota_superior_mm"],
                                "cota_inferior_mm":f["cota_superior_mm"]-f["alto_mm"]} for f in fundaciones]}

    salida = []
    for eje in datos["ejes"]:
        resuelto = deepcopy(eje)
        resuelto["unidades"] = "mm"
        if eje["tipo"] == "apoyo":
            resuelto.update(estacion(eje["nodo"],0))
            salida.append(resuelto)
            continue
        cadena = nodos_de_cadena(eje,tramos)
        puntos = [[nodos[n][k] for k in "xyz"] for n in cadena]
        resuelto.update(nodos=cadena,puntos_directriz=puntos,es_recto=_es_recto(puntos),estaciones=[estacion(cadena[0],0)],segmentos=[])
        acumulada = 0.0
        for indice,ref in enumerate(eje["tramos"]):
            tramo = tramos[ref]
            a,b = nodos[tramo["desde"]],nodos[tramo["hasta"]]
            largo = math.hypot(b["x"]-a["x"],b["y"]-a["y"])
            invertido = cadena[indice] != tramo["desde"]
            rasante = tramo.get("rasante",[{"t":0,"f":0},{"t":1,"f":1}])
            familia = datos["familias"][tramo["familia"]]
            cantos = familia.get("perfil_canto") or [{"t":0,"canto_mm":familia["canto_mm"]},
                      {"t":1,"canto_mm":familia.get("canto_fin_mm",familia["canto_mm"])}]
            ini,fin = tramo.get("retranqueo_inicio_mm",0)/largo,1-tramo.get("retranqueo_fin_mm",0)/largo
            ts = sorted({ini,fin}|{p["t"] for p in rasante+cantos if ini<p["t"]<fin},reverse=invertido)
            def abscisa(t):
                return acumulada+(1-t if invertido else t)*largo
            perfil = [{"estacion_mm":abscisa(t),"z_mm":a["z"]+(b["z"]-a["z"])*_interpolar(rasante,t,"f"),
                       "x_mm":a["x"]+(b["x"]-a["x"])*t,"y_mm":a["y"]+(b["y"]-a["y"])*t,"t_tramo":t} for t in ts]
            resuelto["segmentos"].append({"tramo":ref,"desde":cadena[indice],"hasta":cadena[indice+1],
                "invertido":invertido,"funcion":tramo.get("funcion"),"familia":tramo["familia"],
                "estacion_inicio_mm":acumulada,"estacion_fin_mm":acumulada+largo,
                "estacion_inicio_util_mm":perfil[0]["estacion_mm"],"estacion_fin_util_mm":perfil[-1]["estacion_mm"],
                "puntos_rasante":perfil,"perfil_canto":[{"estacion_mm":abscisa(t),"canto_mm":_interpolar(cantos,t,"canto_mm")} for t in ts]})
            acumulada += largo
            resuelto["estaciones"].append(estacion(cadena[indice+1],acumulada))
        resuelto["longitud_mm"] = acumulada
        salida.append(resuelto)
    return salida
