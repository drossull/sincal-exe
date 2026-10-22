"""Contrato y resolución geométrica de pasarelas, sin dependencias de FreeCAD.

Las longitudes se expresan en milímetros. La validación comprueba coherencia de
datos y geometría; no constituye un cálculo resistente ni una aprobación del
proyecto. Las discrepancias documentales se conservan como avisos.
"""

from __future__ import annotations

from .seccion import familia_del_tramo

from collections import Counter, defaultdict, deque
from copy import deepcopy
import math
from .proyecto import convertir_a_interno, validar_georreferencia
from .ejes import validar_ejes, resolver_ejes


def _numero(valor):
    try:
        return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)
    except OverflowError:
        return False


def _texto(valor):
    return isinstance(valor, str) and bool(valor.strip())


def _perfil(tramo):
    return tramo.get("rasante", [{"t": 0.0, "f": 0.0}, {"t": 1.0, "f": 1.0}])


def _marco_fundacion(fundacion, nodos):
    """Marco local del dado; devuelve None si sus datos aún no son interpretables."""
    referencias = fundacion.get("nodos")
    if not isinstance(referencias, list) or not referencias:
        return None
    if not all(_texto(n) and n in nodos and all(_numero(nodos[n].get(e)) for e in "xy") for n in referencias):
        return None
    miembros = [nodos[n] for n in referencias]
    centro = [sum(n[e] / len(miembros) for n in miembros) for e in "xy"]
    angulo = fundacion.get("angulo_deg")
    if angulo is None:
        angulo = math.degrees(math.atan2(miembros[-1]["y"] - miembros[0]["y"],
                                        miembros[-1]["x"] - miembros[0]["x"])) if len(miembros) > 1 else 0.0
    if not all(_numero(v) for v in (*centro, angulo)):
        return None
    return centro, angulo


def _canto_extremo(familia, final):
    perfil = familia.get("perfil_canto")
    if perfil is not None:
        if not isinstance(perfil, list) or not perfil or not isinstance(perfil[-1 if final else 0], dict):
            return None
        return perfil[-1 if final else 0].get("canto_mm")
    return familia.get("canto_fin_mm", familia.get("canto_mm")) if final else familia.get("canto_mm")


def interpolar_rasante(rasante, t):
    """Devuelve el progreso vertical f para t, sobre una rasante ya validada."""
    if not _numero(t) or not 0 <= t <= 1:
        raise ValueError("t debe ser un número finito entre 0 y 1")
    for anterior, siguiente in zip(rasante, rasante[1:]):
        if t <= siguiente["t"]:
            proporcion = (t - anterior["t"]) / (siguiente["t"] - anterior["t"])
            return anterior["f"] + proporcion * (siguiente["f"] - anterior["f"])
    return rasante[-1]["f"]


def _comprobar_galibos(modelo, nodos, familias):
    """Conserva el requisito de gálibo sin inferir una superficie de calzada.

    Una cota proyectada en el centro de un apoyo no describe el pavimento bajo
    el atravieso. Tampoco las cotas globales de archivos antiguos autorizan una
    comprobación: se conservan para intercambio, sin tratarlas como un plano.
    """
    proyecto = modelo.get("proyecto", {})
    if not isinstance(proyecto, dict):
        return []
    return [{"tipo": "galibo_geometrico", "tramo": tramo.get("id"),
             "objetivo_m": proyecto.get("galibo_m"), "estado": "pendiente",
             "alcance": "Las cotas de terreno proyectado pertenecen al centro de cada apoyo; no definen el pavimento bajo el atravieso",
             "mensaje": "Gálibo pendiente de comprobación: las cotas de terreno en los apoyos no definen la superficie de circulación"}
            for tramo in modelo.get("tramos", [])
            if isinstance(tramo, dict) and tramo.get("funcion") == "cruce"]


def validar(modelo, borrador=False):
    """Valida v1/mm o v2/m; borrador separa pendientes de datos inválidos.

    Un nodo estructural pertenece a un solo dado y tiene exactamente un soporte.
    El grafo peatonal se forma exclusivamente con tramos: compartir una fundación
    no une dos recorridos. Las bifurcaciones y circuitos conectados se admiten con
    aviso; ``recorrido`` sólo se llena para un camino simple, preferentemente E1→E2.
    """
    errores, avisos, pendientes_estructurales, comprobaciones = [], [], [], []
    resumen = dict.fromkeys(("nodos", "tramos", "vigas", "retornos", "fustes", "estribos", "dados", "pilotes"), 0)

    def incidencia(lista, codigo, elemento, mensaje):
        lista.append({"codigo": codigo, "elemento": str(elemento), "mensaje": mensaje})

    def error(codigo, elemento, mensaje, pendiente=False):
        if pendiente:
            incidencia(pendientes_estructurales, codigo, elemento, mensaje)
        if not pendiente or not borrador:
            incidencia(errores, codigo, elemento, mensaje)

    def aviso(codigo, elemento, mensaje):
        incidencia(avisos, codigo, elemento, mensaje)

    def resultado(recorrido=None):
        return {"valido": not errores, "errores": errores, "avisos": avisos,
                "generable": not errores and not pendientes_estructurales,
                "pendientes": pendientes_estructurales, "borrador": bool(borrador),
                "comprobaciones": comprobaciones,
                "resumen": resumen, "recorrido": recorrido or []}

    if not isinstance(modelo, dict):
        error("modelo_invalido", "$", "El modelo debe ser un objeto JSON")
        return resultado()
    if type(modelo.get("version")) is int and modelo["version"] == 2:
        try:
            modelo = convertir_a_interno(modelo)
        except (ValueError, TypeError, OverflowError) as exc:
            error("formato_portable_invalido", "proyecto", str(exc))
            return resultado()
    if type(modelo.get("version")) is not int or modelo.get("version") != 1:
        error("version_invalida", "version", "Se requiere la versión entera 1")
    proyecto = modelo.get("proyecto")
    exige_funcion = isinstance(proyecto,dict) and proyecto.get("esquema_intercambio") == 2
    if not isinstance(proyecto, dict):
        error("proyecto_invalido", "proyecto", "El proyecto debe ser un objeto")
    else:
        for clave in ("id", "nombre", "estado"):
            if not _texto(proyecto.get(clave)):
                error("dato_requerido", "proyecto", f"Falta un texto válido en proyecto.{clave}")
        if "uuid" in proyecto and not _texto(proyecto["uuid"]):
            error("uuid_invalido","proyecto","uuid debe ser un identificador estable no vacío")
        if proyecto.get("unidades") != "mm":
            error("unidades_invalidas", "proyecto", "Las unidades internas deben ser mm")
        for clave in ("galibo_m", "cota_carretera_m"):
            valor = proyecto.get(clave)
            if valor is not None and (not _numero(valor) or clave == "galibo_m" and valor <= 0):
                error("referencia_viaria_invalida", "proyecto", f"{clave} debe ser finito" + (" y positivo" if clave == "galibo_m" else ""))
        reglas = proyecto.get("reglas",{})
        if not isinstance(reglas,dict):
            error("reglas_invalidas","proyecto","reglas debe ser un objeto")
        elif "pendiente_rampas_pct" in reglas and (not _numero(reglas["pendiente_rampas_pct"]) or reglas["pendiente_rampas_pct"] != 8):
            error("pendiente_fija_no_modificable","proyecto","La pendiente fija de las rampas es 8%; no admite otro valor en el JSON")
    georreferencia = proyecto.get("georreferencia",modelo.get("georreferencia")) if isinstance(proyecto,dict) else modelo.get("georreferencia")
    if "georreferencia" in modelo or isinstance(proyecto,dict) and "georreferencia" in proyecto:
        for mensaje in validar_georreferencia(georreferencia):
            error("georreferencia_invalida", "georreferencia", mensaje)
    if isinstance(proyecto,dict) and "georreferencia" in proyecto and "georreferencia" in modelo and proyecto["georreferencia"] != modelo["georreferencia"]:
        error("georreferencia_ambigua","georreferencia","Las referencias en proyecto y raíz difieren; conserve una referencia explícita")

    def lista(clave):
        datos = modelo.get(clave)
        if not isinstance(datos, list):
            error("lista_invalida", clave, f"{clave} debe ser una lista")
            return []
        salida = []
        for indice, dato in enumerate(datos):
            if not isinstance(dato, dict):
                error("entidad_invalida", f"{clave}[{indice}]", "La entidad debe ser un objeto")
            else:
                salida.append(dato)
        return salida

    nodos = lista("nodos")
    tramos = lista("tramos")
    fundaciones = lista("fundaciones")
    soportes = lista("soportes")
    familias = modelo.get("familias")
    if not isinstance(familias, dict):
        error("familias_invalidas", "familias", "Las familias deben formar un objeto")
        familias = {}
    for clave in ("pendientes_documentales", "vistas"):
        if clave in modelo and not isinstance(modelo[clave], list):
            error("lista_invalida", clave, f"{clave} debe ser una lista")
    pendientes = modelo.get("pendientes_documentales", [])
    if isinstance(pendientes, list):
        for indice, pendiente in enumerate(pendientes):
            if not _texto(pendiente):
                error("pendiente_invalido", f"pendientes_documentales[{indice}]", "El pendiente debe ser un texto no vacío")
            else:
                aviso("pendiente_documental", "proyecto", pendiente)

    ids, uuids = {}, set()

    def registrar_uuid(entidad,categoria,elemento):
        if "uuid" not in entidad:
            return
        valor = entidad["uuid"]
        if not _texto(valor):
            error("uuid_invalido",elemento,"uuid debe ser un identificador estable no vacío")
            return
        clave = ("pilotes" if categoria.startswith("pilotes") else categoria,valor)
        if clave in uuids:
            error("uuid_duplicado",elemento,"Dos entidades del mismo tipo no pueden compartir uuid")
        uuids.add(clave)

    def registrar(entidad, categoria, posicion):
        identificador = entidad.get("id")
        if not _texto(identificador):
            error("id_invalido", f"{categoria}[{posicion}]", "Se requiere un identificador no vacío")
            return None
        if identificador in ids:
            error("id_duplicado", identificador, f"Identificador compartido por {ids[identificador]} y {categoria}")
        else:
            ids[identificador] = categoria
        registrar_uuid(entidad,categoria,identificador)
        return identificador

    def dimension(entidad, clave, elemento, *, cero=False, defecto=None):
        valor = entidad.get(clave, defecto)
        if not _numero(valor) or (valor < 0 if cero else valor <= 0):
            limite = "no negativo" if cero else "positivo"
            error("dimension_invalida", elemento, f"{clave} debe ser un número finito {limite}", pendiente=valor is None)
            return None
        return float(valor)

    nodos_id = {}
    for indice, nodo in enumerate(nodos):
        identificador = registrar(nodo, "nodos", indice)
        elemento = identificador or f"nodos[{indice}]"
        if identificador and identificador not in nodos_id:
            nodos_id[identificador] = nodo
        if nodo.get("tipo") not in ("columna", "estribo", "encuentro"):
            error("tipo_nodo_invalido", elemento, "El tipo de nodo debe ser columna, estribo o encuentro")
        for eje in "xyz":
            if not _numero(nodo.get(eje)):
                error("coordenada_invalida", elemento, f"La coordenada {eje} debe ser finita", pendiente=nodo.get(eje) is None)
    if not nodos:
        error("sin_nodos", "nodos", "El modelo necesita al menos un nodo", pendiente=True)
    if not tramos:
        error("sin_tramos", "tramos", "Dibuje al menos un tramo para generar geometría", pendiente=True)

    adyacencias = {identificador: [] for identificador in nodos_id}
    intrados_por_nodo = defaultdict(list)
    for indice, tramo in enumerate(tramos):
        identificador = registrar(tramo, "tramos", indice)
        elemento = identificador or f"tramos[{indice}]"
        tipo = tramo.get("tipo")
        if tipo not in ("viga", "retorno"):
            error("tipo_tramo_invalido", elemento, "El tipo de tramo debe ser viga o retorno")
        funcion = tramo.get("funcion")
        if funcion is None:
            if exige_funcion:
                error("funcion_requerida",elemento,"Clasifique la función del tramo para verificar pendientes",pendiente=True)
            else:
                aviso("funcion_legacy_sin_verificar",elemento,
                      "Tramo heredado sin función: pendiente de clasificar para comprobar la regla geométrica del 8%; conserva sus cotas de referencia")
        if funcion is not None and funcion not in ("cruce", "rampa", "descanso", "retorno", "escalera"):
            error("funcion_tramo_invalida", elemento, "funcion debe ser cruce, rampa, descanso, retorno o escalera")
        ancho = dimension(tramo, "ancho_mm", elemento)
        retranqueos = [dimension(tramo, clave, elemento, cero=True, defecto=0)
                      for clave in ("retranqueo_inicio_mm", "retranqueo_fin_mm")]
        extremos = []
        for clave in ("desde", "hasta"):
            referencia = tramo.get(clave)
            if not _texto(referencia) or referencia not in nodos_id:
                error("referencia_nodo", elemento, f"{clave} no identifica un nodo existente", pendiente=referencia in (None, ""))
                extremos.append(None)
            else:
                extremos.append(nodos_id[referencia])
        longitud = None
        if all(extremos):
            desde, hasta = tramo["desde"], tramo["hasta"]
            adyacencias[desde].append(hasta)
            adyacencias[hasta].append(desde)
            if all(_numero(n.get(eje)) for n in extremos for eje in "xy"):
                longitud = math.hypot(extremos[1]["x"] - extremos[0]["x"], extremos[1]["y"] - extremos[0]["y"])
                if not math.isfinite(longitud):
                    error("longitud_invalida", elemento, "La separación entre nodos debe ser representable como longitud finita")
                    longitud = None
                elif longitud <= 0:
                    error("tramo_sin_longitud", elemento, "Los extremos necesitan separación en planta")
                elif all(v is not None for v in retranqueos) and sum(retranqueos) >= longitud:
                    error("retranqueos_excesivos", elemento, "Los retranqueos deben dejar una longitud útil positiva")

        perfil = _perfil(tramo)
        if "descanso_central_mm" in tramo:
            if tramo["descanso_central_mm"] != 1500 or longitud is None or longitud <= 1500:
                error("descanso_central", elemento, "El descanso central debe medir 1,50 m y caber entre dos sectores inclinados")
            else:
                esperado = [(0,0), ((longitud-1500)/2/longitud,.5), ((longitud+1500)/2/longitud,.5), (1,1)]
                if not isinstance(perfil,list) or len(perfil)!=4 or any(not isinstance(p,dict) or not _numero(p.get(k)) or abs(p[k]-v)>1e-8 for p,(t,f) in zip(perfil,esperado) for k,v in (("t",t),("f",f))):
                    error("descanso_central", elemento, "La rasante debe conservar el descanso de 1,50 m centrado en la longitud de la viga")
        perfil_valido = isinstance(perfil, list) and len(perfil) >= 2
        if perfil_valido:
            perfil_valido = all(isinstance(p, dict) and _numero(p.get("t")) and _numero(p.get("f"))
                                and 0 <= p["t"] <= 1 and 0 <= p["f"] <= 1 for p in perfil)
        if not perfil_valido:
            error("rasante_invalida", elemento, "La rasante requiere al menos dos pares t,f finitos entre 0 y 1")
        else:
            if any(perfil[0][k] != 0 or perfil[-1][k] != 1 for k in ("t", "f")):
                error("extremos_rasante", elemento, "La rasante debe comenzar en (0,0) y terminar en (1,1)")
            if any(b["t"] <= a["t"] or b["f"] < a["f"] for a, b in zip(perfil, perfil[1:])):
                error("orden_rasante", elemento, "t debe crecer estrictamente y f no puede disminuir")
            elif longitud is not None and longitud > 0 and all(extremos) and all(_numero(n.get("z")) for n in extremos):
                desnivel = extremos[1]["z"]-extremos[0]["z"]
                inclinados = [abs(desnivel*(b["f"]-a["f"])/(longitud*(b["t"]-a["t"])))*100
                              for a,b in zip(perfil,perfil[1:]) if abs(desnivel*(b["f"]-a["f"])) > 1e-7]
                if funcion in ("rampa","cruce") and any(abs(p-8.0)>1e-6 for p in inclinados):
                    error("pendiente_fija_8",elemento,"Cada segmento inclinado de rampa o cruce debe tener pendiente absoluta del 8%")
                if funcion == "rampa" and not inclinados:
                    error("rampa_sin_desnivel",elemento,"Una rampa necesita desnivel; use descanso para un tramo horizontal")
                if funcion in ("descanso","retorno") and abs(desnivel)>1e-6:
                    error("descanso_inclinado",elemento,"Los descansos y retornos deben ser horizontales")

        nombre_familia = tramo.get("familia")
        familia = familias.get(nombre_familia) if _texto(nombre_familia) else None
        if not isinstance(familia, dict):
            error("referencia_familia", elemento, "La familia del tramo no existe o no es un objeto", pendiente=nombre_familia in (None, ""))
            continue
        tipo_seccion = familia.get("tipo", "maciza" if tipo == "retorno" else "cajon")
        if tipo_seccion not in ("maciza", "cajon", "escalera"):
            error("tipo_familia_invalido", elemento, "El tipo de familia debe ser maciza, cajon o escalera")
        if funcion == "escalera" and tipo_seccion != "escalera":
            error("familia_escalera_requerida", elemento, "La función escalera requiere una familia de sección escalera")
        if tipo_seccion == "escalera":
            numero = familia.get("numero_peldanos")
            if type(numero) is not int or not 1 <= numero <= 500:
                error("peldanos_invalidos", elemento, "numero_peldanos debe ser entero de 1 a 500", pendiente=numero is None)
            if funcion not in (None, "escalera"):
                error("funcion_escalera_incompatible", elemento, "La familia escalera debe tener función escalera")
            if perfil != [{"t":0,"f":0},{"t":1,"f":1}]:
                error("rasante_escalera", elemento, "La escalera recta necesita rasante lineal; modele descansos como tramos separados")
            if "perfil_canto" in familia or familia.get("canto_fin_mm",familia.get("canto_mm")) != familia.get("canto_mm"):
                error("canto_escalera", elemento, "La losa de escalera requiere canto constante")
            if all(extremos) and all(_numero(n.get("z")) for n in extremos) and abs(extremos[1]["z"]-extremos[0]["z"]) < 1e-6:
                error("escalera_sin_desnivel", elemento, "La escalera necesita un desnivel positivo entre extremos")
        familia = familia_del_tramo(familia, tramo, nodos_id)
        canto = dimension(familia, "canto_mm", elemento)
        if tipo_seccion == "maciza" and "ancho_inferior_mm" in familia:
            dimension(familia,"ancho_inferior_mm",elemento)
        for final, nodo in enumerate(extremos):
            canto_extremo = _canto_extremo(familia, bool(final))
            if nodo is not None and _numero(nodo.get("z")) and _numero(canto_extremo) and canto_extremo > 0:
                intrados_por_nodo[nodo["id"]].append(nodo["z"] - canto_extremo)
        cantos = [canto] if canto is not None else []
        if "canto_fin_mm" in familia:
            canto_fin = dimension(familia, "canto_fin_mm", elemento)
            if canto_fin is not None:
                cantos.append(canto_fin)
        if "perfil_canto" in familia:
            perfil_canto = familia["perfil_canto"]
            valido_canto = isinstance(perfil_canto, list) and len(perfil_canto) >= 2
            if valido_canto:
                valido_canto = all(isinstance(p, dict) and _numero(p.get("t")) and 0 <= p["t"] <= 1
                                  and _numero(p.get("canto_mm")) and p["canto_mm"] > 0 for p in perfil_canto)
            if not valido_canto:
                error("perfil_canto_invalido", elemento, "perfil_canto requiere al menos dos puntos t,canto_mm finitos y canto positivo")
            else:
                cantos.extend(p["canto_mm"] for p in perfil_canto)
                if perfil_canto[0]["t"] != 0 or perfil_canto[-1]["t"] != 1:
                    error("extremos_perfil_canto", elemento, "perfil_canto debe abarcar t=0 hasta t=1")
                if any(b["t"] <= a["t"] for a, b in zip(perfil_canto, perfil_canto[1:])):
                    error("orden_perfil_canto", elemento, "Los valores t de perfil_canto deben crecer estrictamente")
        pendiente = familia.get("pendiente_transversal_pct", 0 if tipo_seccion == "escalera" else 1)
        if not _numero(pendiente) or pendiente < 0:
            error("pendiente_transversal", elemento, "La pendiente transversal debe ser finita y no negativa")
        elif tipo_seccion == "escalera" and pendiente != 0:
            error("pendiente_transversal", elemento, "La pendiente transversal no está disponible para escaleras")
        elif tipo_seccion != "escalera" and pendiente != 1:
            error("pendiente_transversal", elemento, "La pendiente transversal debe ser 1 % a dos aguas")
        elif ancho is not None and cantos:
            espesor = familia.get("losa_superior_mm") if tipo_seccion == "cajon" else min(cantos)
            if _numero(espesor) and pendiente*ancho/200 >= espesor:
                error("pendiente_transversal", elemento, "La pendiente transversal agota el espesor en los bordes")
        if tipo_seccion == "cajon":
            medidas = {k: dimension(familia, k, elemento) for k in (
                "ancho_inferior_mm", "ancho_alma_superior_mm", "losa_superior_mm", "losa_inferior_mm", "alma_mm")}
            dimension(familia, "ala_mm", elemento, cero=True, defecto=0)
            macizado = dimension(familia, "macizado_mm", elemento, cero=True, defecto=500)
            if macizado is not None and macizado != 500:
                error("macizado_fijo", elemento, "El macizado debe ser 0,50 m en cada extremo")
            if canto is not None and all(v is not None for v in medidas.values()):
                if medidas["losa_superior_mm"] + medidas["losa_inferior_mm"] >= min(cantos):
                    error("cajon_sin_hueco", elemento, "Las losas superior e inferior consumen el canto del cajón")
                if 2 * medidas["alma_mm"] >= min(medidas["ancho_inferior_mm"], medidas["ancho_alma_superior_mm"]):
                    error("cajon_sin_hueco", elemento, "El espesor de almas elimina el hueco transversal")
                if ancho is not None and max(medidas["ancho_inferior_mm"], medidas["ancho_alma_superior_mm"]) > ancho:
                    error("cajon_fuera_tablero", elemento, "El ancho del cajón supera el ancho del tramo")
            if longitud is not None and all(v is not None for v in retranqueos) and macizado is not None:
                if macizado > 0 and 2 * macizado >= longitud - sum(retranqueos):
                    error("macizados_excesivos", elemento, "Los macizados de ambos extremos deben dejar longitud de cajón hueca")

    fundaciones_id = {}
    pertenencias = defaultdict(list)
    marcos_dados = {}
    total_pilotes = 0
    for indice, fundacion in enumerate(fundaciones):
        identificador = registrar(fundacion, "fundaciones", indice)
        elemento = identificador or f"fundaciones[{indice}]"
        if identificador and identificador not in fundaciones_id:
            fundaciones_id[identificador] = fundacion
        medidas_dado = {clave: dimension(fundacion, clave, elemento) for clave in ("largo_mm", "ancho_mm", "alto_mm")}
        if not _numero(fundacion.get("cota_superior_mm")):
            error("cota_invalida", elemento, "cota_superior_mm debe ser finita", pendiente=fundacion.get("cota_superior_mm") is None)
        if "angulo_deg" in fundacion and not _numero(fundacion["angulo_deg"]):
            error("angulo_invalido", elemento, "angulo_deg debe ser finito")
        miembros = fundacion.get("nodos")
        if not isinstance(miembros, list) or not miembros:
            error("nodos_fundacion", elemento, "La fundación necesita una lista no vacía de nodos")
            miembros = []
        vistos = set()
        for miembro in miembros:
            if not _texto(miembro) or miembro not in nodos_id:
                error("referencia_nodo", elemento, "La fundación referencia un nodo inexistente")
            elif miembro in vistos:
                error("pertenencia_duplicada", elemento, f"El nodo {miembro} se repite en la misma fundación")
            else:
                vistos.add(miembro)
                pertenencias[miembro].append(identificador)
        marco = _marco_fundacion(fundacion, nodos_id)
        if marco is not None and identificador and identificador not in marcos_dados:
            marcos_dados[identificador] = marco
        pilotes = fundacion.get("pilotes", [])
        if not isinstance(pilotes, list):
            error("pilotes_invalidos", elemento, "pilotes debe ser una lista")
            pilotes = []
        for numero_pilote, pilote in enumerate(pilotes):
            if not isinstance(pilote, dict):
                error("pilote_invalido", elemento, "Cada pilote debe ser un objeto")
                continue
            total_pilotes += 1
            id_pilote = registrar(pilote, f"pilotes de {elemento}", numero_pilote) or elemento
            diametro = dimension(pilote, "diametro_mm", id_pilote)
            dimension(pilote, "longitud_mm", id_pilote)
            for clave in ("dx_mm", "dy_mm"):
                if not _numero(pilote.get(clave)):
                    error("coordenada_invalida", id_pilote, f"{clave} debe ser finito")
            if diametro is not None and all(_numero(pilote.get(k)) for k in ("dx_mm", "dy_mm")) and all(v is not None for v in medidas_dado.values()):
                if (abs(pilote["dx_mm"]) + diametro / 2 > medidas_dado["largo_mm"] / 2 + 1e-6 or
                        abs(pilote["dy_mm"]) + diametro / 2 > medidas_dado["ancho_mm"] / 2 + 1e-6):
                    error("pilote_fuera_dado", id_pilote, "La huella circular del pilote debe quedar contenida en el dado")
    referencias_soportes = {s.get("nodo") for s in soportes if _texto(s.get("nodo"))}
    for identificador, nodo in nodos_id.items():
        cantidad = len(pertenencias[identificador])
        requiere = nodo.get("tipo") in ("columna", "estribo") or identificador in referencias_soportes
        if requiere and cantidad != 1:
            error("pertenencia_fundacion", identificador, f"El nodo con soporte debe pertenecer a una sola fundación; pertenece a {cantidad}", pendiente=cantidad == 0)
        elif not requiere and cantidad:
            error("fundacion_sin_soporte", identificador, "Una fundación sólo puede incluir nodos con soporte", pendiente=True)

    soportes_por_nodo = Counter()
    ids_soportes = set()
    for indice, soporte in enumerate(soportes):
        identificador = soporte.get("id")
        elemento = identificador if _texto(identificador) else f"soportes[{indice}]"
        registrar_uuid(soporte,"soportes",elemento)
        if not _texto(identificador):
            error("id_invalido", elemento, "El soporte necesita identificador")
        elif identificador in ids_soportes:
            error("id_duplicado", elemento, "Se repite el identificador de soporte")
        else:
            ids_soportes.add(identificador)
        if "cota_terreno_proyectado_mm" not in soporte:
            aviso("terreno_proyectado_pendiente", elemento,
                  "Falta definir la cota de terreno proyectado en el centro de este apoyo")
        elif not _numero(soporte["cota_terreno_proyectado_mm"]):
            error("cota_terreno_proyectado_invalida", elemento,
                  "La cota de terreno proyectado en el centro del apoyo debe ser un número finito; omita el campo si está pendiente")
        referencia = soporte.get("nodo")
        nodo = nodos_id.get(referencia) if _texto(referencia) else None
        if nodo is None:
            error("referencia_nodo", elemento, "El soporte referencia un nodo inexistente")
        else:
            soportes_por_nodo[referencia] += 1
            if identificador != referencia:
                error("id_soporte", elemento, "El id del soporte debe coincidir con el id del nodo")
            if nodo.get("tipo") in ("columna", "encuentro"):
                dimension(soporte, "diametro_mm", elemento)
            elif nodo.get("tipo") == "estribo":
                dimension(soporte, "ancho_mm", elemento)
                dimension(soporte, "largo_mm", elemento)
        id_fundacion = soporte.get("fundacion")
        fundacion = fundaciones_id.get(id_fundacion) if _texto(id_fundacion) else None
        if fundacion is None:
            error("referencia_fundacion", elemento, "El soporte referencia una fundación inexistente", pendiente=id_fundacion in (None, ""))
        elif nodo is not None and id_fundacion not in pertenencias[referencia]:
            error("soporte_fuera_fundacion", elemento, "El nodo del soporte no pertenece a su fundación")
        cota = soporte.get("cota_superior_mm")
        if not _numero(cota):
            error("cota_invalida", elemento, "cota_superior_mm debe ser finita", pendiente=cota is None)
        else:
            if nodo is not None and _numero(nodo.get("z")) and cota >= nodo["z"]:
                error("soporte_sobre_rasante", elemento, "El soporte debe terminar por debajo de la superficie de paso")
            if nodo is not None and intrados_por_nodo[referencia] and cota > min(intrados_por_nodo[referencia]) + 1e-6:
                error("soporte_atraviesa_intrados", elemento, "La cabeza del soporte supera el intradós de un tramo incidente")
            if fundacion is not None and _numero(fundacion.get("cota_superior_mm")) and cota <= fundacion["cota_superior_mm"]:
                error("soporte_sin_altura", elemento, "El soporte debe terminar sobre la cara superior del dado")
            elif fundacion is not None and _numero(fundacion.get("cota_superior_mm")) and not _numero(cota - fundacion["cota_superior_mm"]):
                error("altura_invalida", elemento, "La altura del soporte debe ser finita")
        if nodo is not None and fundacion is not None and id_fundacion in marcos_dados:
            centro, angulo = marcos_dados[id_fundacion]
            coseno, seno = math.cos(math.radians(angulo)), math.sin(math.radians(angulo))
            if all(_numero(nodo.get(e)) for e in "xy"):
                dx, dy = nodo["x"] - centro[0], nodo["y"] - centro[1]
                x_local, y_local = dx * coseno + dy * seno, -dx * seno + dy * coseno
                largo, ancho = fundacion.get("largo_mm"), fundacion.get("ancho_mm")
                if nodo.get("tipo") in ("columna", "encuentro"):
                    diametro = soporte.get("diametro_mm")
                    semilargo = semiancho = diametro / 2 if _numero(diametro) and diametro > 0 else None
                else:
                    largo_soporte, ancho_soporte = soporte.get("largo_mm"), soporte.get("ancho_mm")
                    semilargo = largo_soporte / 2 if _numero(largo_soporte) and largo_soporte > 0 else None
                    semiancho = ancho_soporte / 2 if _numero(ancho_soporte) and ancho_soporte > 0 else None
                if all(_numero(v) for v in (largo, ancho, semilargo, semiancho)):
                    if (not _numero(x_local) or not _numero(y_local) or
                            abs(x_local) + semilargo > largo / 2 + 1e-6 or abs(y_local) + semiancho > ancho / 2 + 1e-6):
                        error("soporte_fuera_dado", elemento, "La huella del soporte debe quedar contenida en el dado orientado")
    for identificador, nodo in nodos_id.items():
        cantidad = soportes_por_nodo[identificador]
        if nodo.get("tipo") in ("columna", "estribo") and cantidad != 1:
            error("cantidad_soportes", identificador, "El nodo necesita exactamente un soporte", pendiente=cantidad == 0)
        elif cantidad > 1:
            error("cantidad_soportes", identificador, "Un encuentro admite como máximo un soporte")

    recorrido = []
    if nodos_id:
        visitados = set()
        pendientes_grafo = deque([next(iter(nodos_id))])
        while pendientes_grafo:
            actual = pendientes_grafo.popleft()
            if actual in visitados:
                continue
            visitados.add(actual)
            pendientes_grafo.extend(v for v in adyacencias[actual] if v not in visitados)
        if len(visitados) != len(nodos_id):
            error("recorrido_desconectado", "tramos", "Los tramos no conectan todos los nodos; compartir dado no crea continuidad peatonal", pendiente=True)
        grados = {n: len(vecinos) for n, vecinos in adyacencias.items()}
        extremos = [n for n, grado in grados.items() if grado == 1]
        if any(grado > 2 for grado in grados.values()):
            aviso("recorrido_bifurcado", "tramos", "El recorrido tiene bifurcaciones; no existe una única ordenación lineal")
        elif len(visitados) == len(nodos_id) and len(extremos) == 2:
            inicio = "E1" if "E1" in extremos else next((e for e in sorted(extremos) if e != "E2"), extremos[0])
            anterior, actual = None, inicio
            while actual is not None and actual not in recorrido:
                recorrido.append(actual)
                siguientes = [v for v in adyacencias[actual] if v != anterior]
                anterior, actual = actual, siguientes[0] if siguientes else None
        elif len(visitados) == len(nodos_id) and len(nodos_id) > 1:
            aviso("recorrido_circuito", "tramos", "El recorrido conectado no es un camino simple; conserve sus conexiones explícitas")
        elif len(nodos_id) == 1:
            recorrido = list(nodos_id)
    resumen.update(nodos=len(nodos), tramos=len(tramos), vigas=sum(t.get("tipo") == "viga" for t in tramos),
                   retornos=sum(t.get("tipo") == "retorno" for t in tramos), dados=len(fundaciones), pilotes=total_pilotes,
                   fustes=sum(nodos_id.get(s.get("nodo") if _texto(s.get("nodo")) else "", {}).get("tipo") == "columna" for s in soportes),
                   estribos=sum(nodos_id.get(s.get("nodo") if _texto(s.get("nodo")) else "", {}).get("tipo") == "estribo" for s in soportes))
    comprobaciones.extend(_comprobar_galibos(modelo,nodos_id,familias))
    for comprobacion in comprobaciones:
        if comprobacion["estado"] == "insuficiente":
            aviso("galibo_insuficiente",comprobacion["tramo"],comprobacion["mensaje"]+
                  f"; inferior al objetivo declarado de {comprobacion['objetivo_m']:g} m")
    ejes = validar_ejes(modelo)
    for incidencia_eje in ejes["errores"]:
        error(**incidencia_eje)
    for incidencia_eje in ejes["pendientes"]:
        error(**incidencia_eje,pendiente=True)
    for incidencia_eje in ejes["avisos"]:
        aviso(**incidencia_eje)
    return resultado(recorrido)


def resolver_modelo(modelo):
    """Copia y enriquece un modelo válido con marcos y coordenadas para adaptadores.

    Añade ``validacion`` y ``nodos_por_id``. Cada tramo recibe ``longitud_planta_mm``,
    ``longitud_util_mm``, ``ux``, ``uy``, ``inicio``, ``fin`` y ``puntos_eje`` (XYZ de
    superficie de paso, recortados por retranqueos y conservando descansos).
    Cada dado recibe ``centro`` XYZ de su cara superior y ``angulo_deg``; cada
    pilote, ``centro`` XYZ de su arranque en la cara inferior del dado. Cada
    soporte recibe ``base_z_mm``, ``altura_mm`` y ``centro`` XYZ de su base.
    ``ejes_resueltos`` contiene estaciones en planta, marcadores de apoyos y
    perfiles desarrollados por cadena; sus coordenadas derivadas están en mm.
    """
    informe = validar(modelo)
    if not informe["valido"]:
        raise ValueError("Modelo inválido: " + "; ".join(f"{e['elemento']}: {e['mensaje']}" for e in informe["errores"]))
    resuelto = convertir_a_interno(modelo)
    nodos = {n["id"]: n for n in resuelto["nodos"]}
    resuelto["validacion"] = informe
    resuelto["nodos_por_id"] = nodos
    for tramo in resuelto["tramos"]:
        a, b = nodos[tramo["desde"]], nodos[tramo["hasta"]]
        dx, dy = b["x"] - a["x"], b["y"] - a["y"]
        longitud = math.hypot(dx, dy)
        tramo["rasante"] = deepcopy(_perfil(tramo))
        inicio = tramo.get("retranqueo_inicio_mm", 0) / longitud
        fin = 1 - tramo.get("retranqueo_fin_mm", 0) / longitud

        def punto(t):
            return [a["x"] + t * dx, a["y"] + t * dy,
                    a["z"] + interpolar_rasante(tramo["rasante"], t) * (b["z"] - a["z"])]

        valores_t = [inicio] + [p["t"] for p in tramo["rasante"] if inicio < p["t"] < fin] + [fin]
        tramo.update(longitud_planta_mm=longitud, longitud_util_mm=(fin - inicio) * longitud,
                     ux=dx / longitud, uy=dy / longitud, inicio=punto(inicio), fin=punto(fin),
                     puntos_eje=[punto(t) for t in valores_t])
        familia = resuelto["familias"][tramo["familia"]]
        if familia.get("tipo") == "escalera":
            tramo.update(huella_mm=tramo["longitud_util_mm"]/familia["numero_peldanos"],
                         contrahuella_mm=abs(tramo["fin"][2]-tramo["inicio"][2])/familia["numero_peldanos"])
    for fundacion in resuelto["fundaciones"]:
        centro, angulo = _marco_fundacion(fundacion, nodos)
        fundacion.update(centro=centro + [fundacion["cota_superior_mm"]], angulo_deg=angulo)
        coseno, seno = math.cos(math.radians(angulo)), math.sin(math.radians(angulo))
        for pilote in fundacion.get("pilotes", []):
            dx, dy = pilote["dx_mm"], pilote["dy_mm"]
            pilote["centro"] = [centro[0] + dx * coseno - dy * seno, centro[1] + dx * seno + dy * coseno,
                                fundacion["cota_superior_mm"] - fundacion["alto_mm"]]
    dados = {d["id"]: d for d in resuelto["fundaciones"]}
    for soporte in resuelto["soportes"]:
        nodo, dado = nodos[soporte["nodo"]], dados[soporte["fundacion"]]
        base = dado["cota_superior_mm"]
        soporte.update(base_z_mm=base, altura_mm=soporte["cota_superior_mm"] - base,
                       centro=[nodo["x"], nodo["y"], base])
    resuelto["ejes_resueltos"] = resolver_ejes(resuelto)
    return resuelto
