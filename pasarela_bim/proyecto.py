"""Intercambio portable en metros y coordenadas locales/georreferenciadas.

El motor conserva v1/mm. Sólo las cinco colecciones geométricas cambian de
unidad; proyecto, emplazamiento, terreno, georreferencia y sus metadatos son
opacos para la conversión y conservan sus magnitudes expresadas en metros.
"""

from copy import deepcopy
import math


COLECCIONES_GEOMETRICAS = ("nodos", "tramos", "familias", "fundaciones", "soportes")
_METADATOS = {"metadatos", "georreferencia", "fuente", "revision"}


def _es_numero(valor):
    try:
        return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)
    except OverflowError:
        return False


def _convertir_campos(valor, sufijo_origen, sufijo_destino, factor):
    if isinstance(valor, list):
        return [_convertir_campos(v, sufijo_origen, sufijo_destino, factor) for v in valor]
    if not isinstance(valor, dict):
        return deepcopy(valor)
    salida = {}
    for clave, dato in valor.items():
        if clave in _METADATOS:
            salida[clave] = deepcopy(dato)
            continue
        nueva = clave[:-len(sufijo_origen)]+sufijo_destino if isinstance(clave, str) and clave.endswith(sufijo_origen) else clave
        if nueva != clave and nueva in valor:
            raise ValueError(f"Magnitud ambigua: {clave} y {nueva} aparecen simultáneamente")
        if nueva != clave:
            convertido = dato * factor if _es_numero(dato) else deepcopy(dato)
            if _es_numero(dato) and not _es_numero(convertido):
                raise ValueError(f"La conversión de {clave} excede el rango numérico")
            salida[nueva] = convertido
        else:
            salida[nueva] = _convertir_campos(dato, sufijo_origen, sufijo_destino, factor)
    return salida


def _convertir(modelo, destino):
    if not isinstance(modelo, dict):
        raise ValueError("El proyecto debe ser un objeto JSON")
    version = modelo.get("version")
    if type(version) is not int or version not in (1, 2):
        raise ValueError("Se requiere versión 1 (mm) o 2 (m)")
    proyecto = modelo.get("proyecto")
    unidad = "mm" if version == 1 else "m"
    if not isinstance(proyecto, dict) or proyecto.get("unidades") != unidad:
        raise ValueError(f"La versión {version} requiere proyecto.unidades='{unidad}'")
    salida = deepcopy(modelo)
    if version == destino:
        return salida
    sufijo_origen, sufijo_destino, factor = ("_m", "_mm", 1000) if destino == 1 else ("_mm", "_m", 0.001)
    for coleccion in COLECCIONES_GEOMETRICAS:
        if coleccion in modelo:
            if coleccion == "familias" and isinstance(modelo[coleccion], dict):
                salida[coleccion] = {k:_convertir_campos(v,sufijo_origen,sufijo_destino,factor)
                                     for k,v in modelo[coleccion].items()}
            else:
                salida[coleccion] = _convertir_campos(modelo[coleccion], sufijo_origen, sufijo_destino, factor)
    if isinstance(salida.get("nodos"), list):
        for nodo in salida["nodos"]:
            if isinstance(nodo, dict):
                for eje in "xyz":
                    if _es_numero(nodo.get(eje)):
                        nodo[eje] *= factor
                        if not _es_numero(nodo[eje]):
                            raise ValueError(f"Coordenada {eje} fuera de rango al convertir unidades")
    salida["version"] = destino
    salida["proyecto"]["unidades"] = "mm" if destino == 1 else "m"
    if version == 2 and destino == 1:
        # Conserva la obligación de clasificar los tramos tras entrar al editor
        # interno; no puede perderse simplemente al cambiar de m a mm.
        salida["proyecto"]["esquema_intercambio"] = 2
    return salida


def convertir_a_interno(modelo):
    """Copia v1/mm; v2 normaliza proyecto.esquema_intercambio=2 como procedencia."""
    return _convertir(modelo, 1)


def convertir_a_portable(modelo):
    """Devuelve copia v2/m, preservando UUID, revisión y metadatos desconocidos."""
    return _convertir(modelo, 2)


def validar_georreferencia(georreferencia):
    """Valida la transformación explícita; no supone ni certifica un CRS."""
    if not isinstance(georreferencia, dict):
        return ["georreferencia debe ser un objeto"]
    errores = []
    for clave in ("este_m", "norte_m", "cota_m", "norte_desde_x_horario_deg"):
        if not _es_numero(georreferencia.get(clave)):
            errores.append(f"georreferencia.{clave} debe ser un número finito")
    angulo = georreferencia.get("norte_desde_x_horario_deg")
    if _es_numero(angulo) and not 0 <= angulo < 360:
        errores.append("norte_desde_x_horario_deg debe estar entre 0 incluido y 360 excluido")
    if "crs" in georreferencia and (not isinstance(georreferencia["crs"], str) or not georreferencia["crs"].strip()):
        errores.append("georreferencia.crs, si se indica, debe ser un texto no vacío")
    return errores


def _marco(georreferencia):
    errores = validar_georreferencia(georreferencia)
    if errores:
        raise ValueError("; ".join(errores))
    angulo = math.radians(georreferencia["norte_desde_x_horario_deg"])
    return math.sin(angulo), math.cos(angulo)


def local_a_global(x_m, y_m, z_m, georreferencia):
    """XYZ locales en m → Este/Norte/cota en m; +Y local apunta arriba en planta.

    Norte horario desde +X: 0° = norte hacia +X, 270° = norte hacia +Y.
    El punto local (0,0,0) coincide con el origen declarado del puente.
    """
    seno, coseno = _marco(georreferencia)
    if not all(_es_numero(v) for v in (x_m, y_m, z_m)):
        raise ValueError("Las coordenadas locales deben ser finitas")
    return {"este_m": georreferencia["este_m"]-seno*x_m-coseno*y_m,
            "norte_m": georreferencia["norte_m"]+coseno*x_m-seno*y_m,
            "cota_m": georreferencia["cota_m"]+z_m}


def global_a_local(este_m, norte_m, cota_m, georreferencia):
    """Inversa exacta del marco plano declarado, sin reproyección cartográfica."""
    seno, coseno = _marco(georreferencia)
    if not all(_es_numero(v) for v in (este_m, norte_m, cota_m)):
        raise ValueError("Las coordenadas globales deben ser finitas")
    e, n = este_m-georreferencia["este_m"], norte_m-georreferencia["norte_m"]
    return {"x": -seno*e+coseno*n, "y": -coseno*e-seno*n,
            "z": cota_m-georreferencia["cota_m"]}
